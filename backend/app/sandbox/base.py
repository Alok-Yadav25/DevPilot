"""Synchronous graph boundary; ActionsAdapter bridges the asynchronous transport."""

from pathlib import Path
from typing import Protocol

from app.agent.state import TestResult


class SandboxRunner(Protocol):
    def preflight(self) -> None: ...
    def run(self, workdir: Path, timeout: float | None = None) -> TestResult: ...
    def close(self) -> None: ...
