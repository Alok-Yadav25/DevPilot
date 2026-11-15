"""The only application entry point for selecting an execution backend."""

import threading
from collections.abc import Callable
from copy import deepcopy
from pathlib import Path
from typing import Any

from app.agent.state import TestResult
from app.config import Settings
from app.errors import DevPilotError
from app.sandbox.base import SandboxRunner as Runner
from app.security import Redactor


class ReplayRunner:
    """Replays are loaded from durable records; never synthesize test success."""

    def play(self, record: dict[str, Any]) -> dict[str, Any]:
        if not record.get("test_evidence"):
            raise DevPilotError(
                "This record has no remote test evidence. It cannot be labelled a real recording."
            )
        return {**deepcopy(record), "mode": "replay"}

    def preflight(self) -> None:
        pass

    def run(self, workdir: Path, timeout: float | None = None) -> TestResult:
        raise DevPilotError("Replay cannot run repository code. Select a recorded run to replay.")

    def close(self) -> None:
        pass


def validate_runner_settings(settings: Settings) -> None:
    if settings.runner_mode == "docker" and settings.app_env != "local":
        raise DevPilotError("The local container runner requires APP_ENV=local.")
    if settings.runner_mode == "github_actions":
        required = {
            "SANDBOX_REPO": settings.sandbox_repo,
            "SANDBOX_GITHUB_TOKEN": settings.sandbox_github_token.get_secret_value(),
            "TARGET_GITHUB_TOKEN": settings.target_github_token.get_secret_value(),
            "ALLOWED_TARGET_REPOS or ALLOWED_TARGET_OWNER": (
                settings.allowed_target_repos or settings.allowed_target_owner
            ),
        }
        missing = [name for name, value in required.items() if not value.strip()]
        if missing:
            raise DevPilotError("GitHub Actions runner setup missing: " + ", ".join(missing))
        if required["SANDBOX_GITHUB_TOKEN"] == required["TARGET_GITHUB_TOKEN"]:
            raise DevPilotError(
                "Sandbox and target tokens must be different, separately scoped tokens."
            )


def make_runner(
    settings: Settings,
    waiting: Callable[[str], None] = lambda message: None,
    cancel: threading.Event | None = None,
) -> Runner:
    validate_runner_settings(settings)
    if settings.runner_mode == "github_actions":
        from app.sandbox.actions_adapter import ActionsAdapter
        from app.sandbox.github_actions import GitHubActionsRunner

        return ActionsAdapter(
            GitHubActionsRunner(
                settings.sandbox_repo,
                settings.sandbox_github_token.get_secret_value(),
                {r.strip() for r in settings.allowed_target_repos.split(",") if r.strip()},
                Redactor(settings.secrets()),
                waiting,
                timeout=settings.actions_timeout_seconds,
                default_branch=settings.sandbox_default_branch,
                cancel=cancel,
                allowed_owner=settings.allowed_target_owner,
            )
        )
    if settings.runner_mode == "docker":
        from app.sandbox.docker_runner import DockerRunner

        return DockerRunner(
            settings.sandbox_image,
            settings.test_timeout_seconds,
            Redactor(settings.secrets()),
            settings.max_repo_bytes,
            settings.max_repo_files,
            cancel=cancel,
        )
    return ReplayRunner()
