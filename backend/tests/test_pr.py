import hashlib
from unittest.mock import MagicMock

import pytest
from app.agent.state import Attempt, RunReport, TestResult
from app.errors import DevPilotError
from app.github.pr import publish_reviewed_patch


def report() -> RunReport:
    diff = "--- a/module.py\n+++ b/module.py\n@@ -1 +1 @@\n-old\n+new\n"
    return RunReport(
        id="approved123",
        repo_url="https://github.com/owner/repo",
        issue_text="Fix the boundary condition",
        status="ready_for_review",
        final_diff=diff,
        review="Review risks.",
        commit_sha="a" * 40,
        attempts=[
            Attempt(
                attempt_no=1,
                patch=diff,
                test_result=TestResult(exit_code=0, outcomes={"test_a": "passed"}),
            )
        ],
    )


def test_publish_only_creates_new_branch_and_draft_pr() -> None:
    run = report()
    github = MagicMock()
    github.request.side_effect = [
        {"default_branch": "main"},
        [],
        None,
        {"tree": {"sha": "base-tree"}},
        {"sha": "new-tree"},
        {"sha": "new-commit"},
        {"ref": "new-branch"},
        {"html_url": "https://github.com/owner/repo/pull/1"},
    ]
    digest = hashlib.sha256(run.final_diff.encode()).hexdigest()
    assert publish_reviewed_patch(github, run, {"module.py": "new\n"}, digest).endswith("/pull/1")
    calls = github.request.call_args_list
    assert all(call.args[0] in {"GET", "POST"} for call in calls)
    ref = calls[6].args[2]
    assert ref["ref"] == "refs/heads/devpilot/fix-approved123"
    assert calls[7].args[2]["draft"] is True
    assert not any("merge" in call.args[1] for call in calls)
    assert calls[5].args[2]["parents"] == [run.commit_sha]


@pytest.mark.parametrize("bad", ["hash", "snapshot", "tests"])
def test_invalid_publication_never_calls_github(bad: str) -> None:
    run = report()
    digest = hashlib.sha256(run.final_diff.encode()).hexdigest()
    snapshot = {"module.py": "new\n"}
    if bad == "hash":
        digest = "0" * 64
    elif bad == "snapshot":
        snapshot = {"tests/test_x.py": "new\n"}
    else:
        run.attempts[-1].test_result.exit_code = 1
    github = MagicMock()
    with pytest.raises(DevPilotError):
        publish_reviewed_patch(github, run, snapshot, digest)
    github.request.assert_not_called()


def test_lost_pr_response_is_reconciled_without_writes():
    run = report()
    digest = hashlib.sha256(run.final_diff.encode()).hexdigest()
    github = MagicMock()
    github.request.side_effect = [
        {"default_branch": "main"},
        [{"body": digest, "html_url": "https://github.com/owner/repo/pull/2"}],
    ]
    assert publish_reviewed_patch(github, run, {"module.py": "new\n"}, digest).endswith("/2")
    assert all(call.args[0] == "GET" for call in github.request.call_args_list)
