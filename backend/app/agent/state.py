from datetime import UTC, datetime
from typing import Any, Literal, TypedDict

from pydantic import BaseModel, Field

Status = Literal["running", "ready_for_review", "unsuitable", "failed", "cancelled", "timeout"]


class TestResult(BaseModel):
    __test__ = False
    exit_code: int
    outcomes: dict[str, str] = Field(default_factory=dict)
    failure_details: dict[str, str] = Field(default_factory=dict)
    output_tail: str = ""
    duration_seconds: float = 0
    timed_out: bool = False
    infrastructure_error: str = ""

    @property
    def passed(self) -> bool:
        return (
            self.exit_code == 0
            and not self.timed_out
            and not self.infrastructure_error
            and bool(self.outcomes)
            and all(
                outcome in {"passed", "skipped", "xfailed"} for outcome in self.outcomes.values()
            )
        )

    @property
    def failures(self) -> list[str]:
        return sorted(
            k for k, v in self.outcomes.items() if v not in {"passed", "skipped", "xfailed"}
        )

    def signature(self) -> str:
        import hashlib
        import json
        import re

        details = {
            name: re.sub(r"0x[0-9a-fA-F]+", "<address>", detail)
            for name, detail in self.failure_details.items()
        }
        return hashlib.sha256(
            json.dumps([self.exit_code, self.outcomes, details], sort_keys=True).encode()
        ).hexdigest()


class Event(BaseModel):
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    node: str
    type: Literal["start", "end", "waiting", "error"]
    message: str
    payload: dict[str, Any] = Field(default_factory=dict)


class Attempt(BaseModel):
    attempt_no: int
    patch: str
    validation_error: str = ""
    test_result: TestResult | None = None


class RunReport(BaseModel):
    id: str
    repo_url: str
    issue_text: str
    status: Status = "running"
    reason: str = ""
    commit_sha: str = ""
    baseline_result: TestResult | None = None
    baseline_results: list[TestResult] = Field(default_factory=list)
    relevant_files: list[str] = Field(default_factory=list)
    hypothesis: str = ""
    final_diff: str = ""
    review: str = ""
    attempts: list[Attempt] = Field(default_factory=list)
    events: list[Event] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    finished_at: datetime | None = None
    model: str = ""


class AgentState(TypedDict, total=False):
    repo_url: str
    issue_text: str
    workdir: str
    baseline_result: TestResult
    relevant_files: list[str]
    hypothesis: str
    patch: str
    attempts: int
    test_result: TestResult
    events: list[Event]
    status: Status
    feedback: str
    context: str
