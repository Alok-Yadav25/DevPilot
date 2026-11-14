"""Bridge the synchronous CLI graph to the asynchronous sandbox interface."""

import asyncio
import time
from pathlib import Path
from uuid import uuid4

from git import Repo

from app.agent.state import TestResult
from app.agent.tools.patches import run_git
from app.errors import DevPilotError
from app.github.clone import validate_repo_url
from app.sandbox.github_actions import GitHubActionsRunner


class ActionsAdapter:
    def __init__(self, runner: GitHubActionsRunner) -> None:
        self.runner = runner
        self.job_id = ""
        self.loop = asyncio.new_event_loop()

    @property
    def limits(self) -> dict[str, str]:
        return self.runner.limits

    def preflight(self) -> None:
        self.loop.run_until_complete(self.runner.preflight())

    def queued_jobs(self) -> int:
        self.runner.deadline = time.monotonic() + 10
        response = self.loop.run_until_complete(
            self.runner.request(
                "GET",
                f"repos/{self.runner.repo}/actions/workflows/run-tests.yml/runs?status=queued&per_page=1",
            )
        )
        return int(response.json()["total_count"])

    def run(self, workdir: Path, timeout: float | None = None) -> TestResult:
        with Repo(workdir) as repo:
            url = validate_repo_url(repo.remotes.origin.url)
            ref = repo.head.commit.hexsha
        target = url.removeprefix("https://github.com/").removesuffix(".git")
        diff = run_git(workdir, "diff", "--no-ext-diff", "--no-textconv", "HEAD", "--")
        self.runner.timeout = min(self.runner.timeout, timeout or self.runner.timeout)
        return self.loop.run_until_complete(
            self.runner.run_tests(self.job_id or uuid4().hex, target, ref, diff)
        )

    def cancel_pending(self) -> None:
        self.loop.run_until_complete(self.runner.cancel_pending())

    def close(self) -> None:
        try:
            self.loop.run_until_complete(self.runner.close())
        finally:
            self.loop.close()


def require_allowed_target(url: str, allowed: str) -> str:
    normalized = validate_repo_url(url.rstrip("/"))
    target = normalized.removeprefix("https://github.com/").removesuffix(".git")
    if target.lower() not in {r.strip().lower() for r in allowed.split(",") if r.strip()}:
        raise DevPilotError("Target repo is not allowlisted. Set ALLOWED_TARGET_REPOS explicitly.")
    return normalized
