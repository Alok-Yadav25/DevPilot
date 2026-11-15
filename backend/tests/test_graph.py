from pathlib import Path

import pytest
from app.agent.graph import Agent
from app.agent.state import TestResult
from app.config import Settings
from app.errors import DevPilotError
from conftest import CASES, Case, FixtureCloner, ScriptedLLM, ScriptedSandbox


def make_agent(
    tmp_path: Path, results: list[TestResult], proposals: list[str], case: Case = CASES[0]
) -> Agent:
    return Agent(
        Settings(_env_file=None, work_root=tmp_path / "work"),
        ScriptedLLM(proposals),
        ScriptedSandbox(results),
        cloner=FixtureCloner(case),
    )


@pytest.mark.parametrize("case", CASES, ids=lambda case: case.name)
def test_workflow_on_three_fixture_repositories(tmp_path: Path, case: Case) -> None:
    agent = make_agent(
        tmp_path, [case.baseline(), case.baseline(), case.success()], [case.proposal()], case
    )
    report = agent.run("https://github.com/fixtures/" + case.name, case.issue, [case.failed])
    assert report.status == "ready_for_review", report.reason
    assert report.final_diff and report.review and len(report.attempts) == 1
    assert report.attempts[0].test_result.passed
    assert list(agent.settings.work_root.iterdir()) == []
    nodes = [event.node for event in report.events if event.type == "start"]
    assert nodes == [
        "clone",
        "baseline",
        "locate",
        "diagnose",
        "patch",
        "validate_patch",
        "test",
        "review",
    ]
    assert not {"push", "open_pr", "merge"} & set(nodes)


def test_retry_uses_original_baseline_then_succeeds(tmp_path: Path) -> None:
    case = CASES[0]
    wrong = case.proposal().replace('return \\"-\\"', 'return \\".\\"')
    agent = make_agent(
        tmp_path,
        [case.baseline(), case.baseline(), case.baseline(), case.success()],
        [wrong, case.proposal()],
    )
    report = agent.run("https://github.com/fixtures/slugify", case.issue)
    assert report.status == "ready_for_review", report.reason
    assert len(report.attempts) == 2
    assert "Retrying" in " ".join(e.message for e in report.events)


def test_repeated_failure_stops_after_two_attempts(tmp_path: Path) -> None:
    case = CASES[0]
    agent = make_agent(tmp_path, [case.baseline()] * 4, [case.proposal()] * 3)
    report = agent.run("https://github.com/fixtures/slugify", case.issue)
    assert report.status == "failed" and "repeated twice" in report.reason
    assert len(report.attempts) == 2


def test_three_invalid_patches_exhaust_budget(tmp_path: Path) -> None:
    case = CASES[0]
    missing_search = case.proposal().replace('return \\"_\\"', 'return \\"missing\\"')
    protected = case.proposal().replace('"slugify.py"', '"test_module.py"')
    agent = make_agent(tmp_path, [case.baseline()] * 2, ["{}", protected, missing_search])
    report = agent.run("https://github.com/fixtures/slugify", case.issue)
    assert report.status == "failed" and "3 patch attempts" in report.reason
    assert len(report.attempts) == 3
    assert all(a.validation_error for a in report.attempts)


@pytest.mark.parametrize(
    "second,reason",
    [
        (CASES[0].success(), "differ"),
        (TestResult(exit_code=4, infrastructure_error="Missing wheel"), "Missing wheel"),
    ],
)
def test_flaky_or_broken_baseline_stops(tmp_path: Path, second: TestResult, reason: str) -> None:
    case = CASES[0]
    agent = make_agent(tmp_path, [case.baseline(), second], [])
    report = agent.run("https://github.com/fixtures/slugify", case.issue)
    assert report.status == "unsuitable" and reason in report.reason
    assert not report.attempts


def test_already_passing_baseline_needs_repro(tmp_path: Path) -> None:
    case = CASES[0]
    report = make_agent(tmp_path, [case.success()] * 2, []).run(
        "https://github.com/fixtures/slugify",
        case.issue,
    )
    assert report.status == "unsuitable" and "regression test" in report.reason


def test_unrelated_baseline_stops(tmp_path: Path) -> None:
    case = CASES[0]
    report = make_agent(tmp_path, [case.baseline()] * 2, []).run(
        "https://github.com/fixtures/slugify",
        case.issue,
        ["tests/test_other.py::test_other"],
    )
    assert report.status == "unsuitable" and "unrelated" in report.reason


def test_disappearing_or_skipped_tests_cannot_succeed(tmp_path: Path) -> None:
    case = CASES[0]
    hidden = TestResult(exit_code=0, outcomes={case.failed: "skipped"})
    report = make_agent(
        tmp_path, [case.baseline(), case.baseline(), hidden], [case.proposal()]
    ).run(
        "https://github.com/fixtures/slugify",
        case.issue,
    )
    assert report.status == "failed" and "inventory" in report.reason


def test_test_timeout_stops_without_retry(tmp_path: Path) -> None:
    case = CASES[0]
    result = TestResult(exit_code=124, timed_out=True)
    report = make_agent(
        tmp_path, [case.baseline(), case.baseline(), result], [case.proposal()]
    ).run(
        "https://github.com/fixtures/slugify",
        case.issue,
    )
    assert report.status == "timeout" and len(report.attempts) == 1


def test_cleanup_after_sandbox_exception(tmp_path: Path) -> None:
    class BrokenSandbox:
        def run(self, workdir: Path, timeout: float | None = None) -> TestResult:
            raise DevPilotError("Docker unavailable")

    agent = make_agent(tmp_path, [], [])
    agent.sandbox = BrokenSandbox()
    report = agent.run("https://github.com/fixtures/slugify", "Fix the separator")
    assert report.status == "failed"
    assert list(agent.settings.work_root.iterdir()) == []
