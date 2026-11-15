import json
import shutil
from dataclasses import dataclass
from pathlib import Path

import pytest
from app.agent.state import TestResult
from app.agent.tools.patches import Change, PatchProposal
from git import Repo

ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Case:
    name: str
    issue: str
    search: str
    replacement: str
    failed: str
    passed: tuple[str, ...]

    def proposal(self) -> str:
        return PatchProposal(
            changes=[
                Change(
                    path=f"{self.name}.py",
                    search=self.search,
                    replace=self.replacement,
                )
            ]
        ).model_dump_json()

    def baseline(self) -> TestResult:
        return TestResult(
            exit_code=1,
            outcomes={
                self.failed: "failed",
                **dict.fromkeys(self.passed, "passed"),
            },
            output_tail=f"FAILED {self.failed} - AssertionError: injected bug",
        )

    def success(self) -> TestResult:
        return TestResult(
            exit_code=0, outcomes=dict.fromkeys([self.failed, *self.passed], "passed")
        )


CASES = [
    Case(
        "slugify",
        "slugify uses underscores instead of hyphens",
        'return "_".join',
        'return "-".join',
        "tests/test_slugify.py::test_separator",
        ("tests/test_slugify.py::test_empty",),
    ),
    Case(
        "clamp",
        "clamp reverses the lower and upper bounds",
        "min(lower, max(upper, value))",
        "max(lower, min(upper, value))",
        "tests/test_clamp.py::test_bounds",
        ("tests/test_clamp.py::test_zero_width",),
    ),
    Case(
        "backoff",
        "backoff's first delay should be 1, not 2",
        "2 ** (attempt + 1)",
        "2 ** attempt",
        "tests/test_backoff.py::test_first_delay",
        ("tests/test_backoff.py::test_cap", "tests/test_backoff.py::test_invalid_attempt"),
    ),
]


def seed_repo(destination: Path, case: Case = CASES[0]) -> Path:
    shutil.copytree(ROOT / "examples" / case.name, destination)
    with Repo.init(destination) as repo:
        repo.index.add(
            [
                str(p.relative_to(destination))
                for p in destination.rglob("*")
                if p.is_file() and ".git" not in p.parts
            ]
        )
        repo.index.commit("Seed a known failing Python test")
    return destination


class FixtureCloner:
    timeout: float = 90

    def __init__(self, case: Case = CASES[0]) -> None:
        self.case = case

    def clone(self, url: str, destination: Path) -> str:
        seed_repo(destination, self.case)
        with Repo(destination) as repo:
            return repo.head.commit.hexsha


class ScriptedLLM:
    """Controller fixture, never a claim of model performance."""

    model = "test-scripted-no-api"

    def __init__(self, proposals: list[str]) -> None:
        self.proposals = iter(proposals)
        self.prompts: list[str] = []

    def complete(self, system: str, prompt: str, deadline: float) -> str:
        self.prompts.append(prompt)
        if '"related":true' in prompt:
            return json.dumps({"related": True, "hypothesis": "Repair the injected source bug."})
        if "search" in system and "changes" in system:
            return next(self.proposals)
        return (
            "A small fix. Tests pass, but passing tests do not prove correctness. "
            "Review edge cases."
        )


class ScriptedSandbox:
    """Supplies outcomes to test graph transitions; executes no repo code."""

    def __init__(self, results: list[TestResult]) -> None:
        self.results = iter(results)
        self.calls = 0

    def run(self, workdir: Path, timeout: float | None = None) -> TestResult:
        self.calls += 1
        return next(self.results).model_copy(deep=True)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    return seed_repo(tmp_path / "repo")
