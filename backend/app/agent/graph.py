import json
import re
import threading
import time
from collections.abc import Callable
from datetime import UTC, datetime
from functools import wraps
from pathlib import Path
from typing import Any, Protocol
from uuid import uuid4

from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, ValidationError

from app.agent.llm import LLM
from app.agent.prompts import PATCH, SYSTEM
from app.agent.state import AgentState, Attempt, Event, RunReport, TestResult
from app.agent.tools.patches import PatchProposal, PatchValidator, reset_to_baseline, run_git
from app.agent.tools.retrieval import check_python_project, failing_output, locate
from app.config import Settings
from app.errors import (
    DevPilotError,
    PatchRejected,
    RunCancelled,
    RunTimeout,
    UnsuitableRepository,
    WorkerPaused,
)
from app.github.clone import Cloner, cleanup_stale, validate_repo_url, workspace
from app.security import Redactor


class Sandbox(Protocol):
    def run(self, workdir: Path, timeout: float | None = None) -> TestResult: ...


class Agent:
    def __init__(
        self,
        settings: Settings,
        llm: LLM,
        sandbox: Sandbox,
        on_event: Callable[[Event], None] | None = None,
        cloner: Cloner | None = None,
        cancel: threading.Event | None = None,
        on_review: Callable[[RunReport, dict[str, str]], None] | None = None,
        on_checkpoint: Callable[[str, dict[str, Any], RunReport], None] | None = None,
    ) -> None:
        self.settings = settings
        self.llm = llm
        self.sandbox = sandbox
        self.redact = Redactor(settings.secrets())
        self.on_event = on_event
        self.cancel = cancel or threading.Event()
        self.pause_requested = threading.Event()
        self.on_review = on_review
        self.on_checkpoint = on_checkpoint
        self.cloner = cloner or Cloner(
            settings.max_repo_bytes,
            settings.max_repo_files,
            settings.clone_timeout_seconds,
        )
        self.cloner.cancel = self.cancel
        self.validator = PatchValidator(
            self.redact,
            settings.max_patch_lines,
            settings.max_patch_files,
        )
        self.deadline = 0.0
        self.expected_failures: set[str] = set()
        self.report = RunReport(id=uuid4().hex[:12], repo_url="", issue_text="", model=llm.model)

    def emit(self, node: str, kind: Any, message: str, **payload: Any) -> None:
        safe_payload = json.loads(self.redact(json.dumps(payload, default=str)))
        event = Event(node=node, type=kind, message=self.redact(message), payload=safe_payload)
        self.report.events.append(event)
        if self.on_event:
            self.on_event(event)

    def remaining(self) -> float:
        if self.pause_requested.is_set():
            raise WorkerPaused("Worker shutting down; the run will resume.")
        if self.cancel.is_set():
            raise RunCancelled("Stopped by the operator. No changes were published.")
        seconds = self.deadline - time.monotonic()
        if seconds <= 0:
            raise RunTimeout("Global run timeout reached. No further attempts were made.")
        return seconds

    def instrument(self, name: str, function: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(function)
        def node(state: AgentState) -> dict[str, Any]:
            self.remaining()
            self.emit(name, "start", f"Starting {name.replace('_', ' ')}.")
            try:
                result: dict[str, Any] = function(state)
                self.remaining()
                details = {
                    key: value.model_dump() if isinstance(value, BaseModel) else value
                    for key, value in result.items()
                    if key
                    in {
                        "baseline_result",
                        "relevant_files",
                        "hypothesis",
                        "attempts",
                        "test_result",
                        "feedback",
                        "status",
                        "patch",
                    }
                }
                if self.on_checkpoint:
                    self.on_checkpoint(name, {**state, **result}, self.report)
                self.emit(name, "end", f"Completed {name.replace('_', ' ')}.", **details)
                return result
            except Exception as exc:
                message = str(exc) if isinstance(exc, DevPilotError) else type(exc).__name__
                self.emit(name, "error", message)
                raise

        return node

    def build_graph(self, start: str = "clone") -> Any:
        graph = StateGraph(AgentState)
        for name in (
            "clone",
            "baseline",
            "locate",
            "diagnose",
            "patch",
            "validate_patch",
            "test",
            "recover",
            "review",
        ):
            graph.add_node(name, self.instrument(name, getattr(self, name)))
        graph.add_edge(START, start)
        graph.add_edge("clone", "baseline")
        graph.add_edge("baseline", "locate")
        graph.add_edge("locate", "diagnose")
        graph.add_edge("diagnose", "patch")
        graph.add_edge("patch", "validate_patch")
        graph.add_conditional_edges(
            "validate_patch", lambda s: "recover" if s.get("feedback") else "test"
        )
        graph.add_conditional_edges(
            "test", lambda s: "review" if s["test_result"].passed else "recover"
        )
        graph.add_conditional_edges(
            "recover", lambda s: END if s["status"] == "failed" else "patch"
        )
        graph.add_edge("review", END)
        return graph.compile()

    def run(
        self,
        repo_url: str,
        issue: str,
        expected_failures: list[str] | None = None,
        resume: dict[str, Any] | None = None,
    ) -> RunReport:
        self.report.repo_url = validate_repo_url(repo_url)
        self.report.issue_text = self.redact(issue)
        if not issue.strip() or len(issue) > 16000:
            raise DevPilotError("Provide a bug description between 1 and 16,000 characters.")
        self.expected_failures = set(expected_failures or [])
        self.deadline = time.monotonic() + self.settings.run_timeout_seconds
        stopped = threading.Event()

        def reaper() -> None:
            while not stopped.wait(300):
                cleanup_stale(self.settings.work_root)

        cleanup_stale(self.settings.work_root)
        sweeper = threading.Thread(target=reaper, daemon=True)
        sweeper.start()
        try:
            with workspace(self.settings.work_root, self.report.id) as workdir:
                state: AgentState = {
                    "repo_url": self.report.repo_url,
                    "issue_text": self.report.issue_text,
                    "workdir": str(workdir),
                    "attempts": 0,
                    "status": "running",
                    "feedback": "",
                }
                start = "clone"
                if resume:
                    self.report = RunReport.model_validate(resume["report"])
                    state.update(resume["state"])
                    state["workdir"] = str(workdir)
                    for key in ("baseline_result", "test_result"):
                        if key in state:
                            state[key] = TestResult.model_validate(state[key])
                    elapsed = (datetime.now(UTC) - self.report.created_at).total_seconds()
                    self.deadline = time.monotonic() + self.settings.run_timeout_seconds - elapsed
                    self.remaining()
                    self.cloner.clone_pinned(repo_url, workdir, self.report.commit_sha)
                    check_python_project(workdir)
                    if state.get("patch", "").startswith("--- a/"):
                        run_git(workdir, "apply", "--check", "-", input_text=state["patch"])
                        run_git(workdir, "apply", "-", input_text=state["patch"])
                    start = self.next_node(resume["node"], state)
                if start != END:
                    self.build_graph(start).invoke(state, config={"recursion_limit": 40})

        except WorkerPaused:
            raise
        except UnsuitableRepository as exc:
            self.report.status, self.report.reason = "unsuitable", self.redact(str(exc))
        except RunTimeout as exc:
            self.report.status, self.report.reason = "timeout", self.redact(str(exc))
        except RunCancelled as exc:
            self.report.status, self.report.reason = "cancelled", self.redact(str(exc))
        except KeyboardInterrupt:
            self.report.status, self.report.reason = "cancelled", "Cancelled by the operator."
        except Exception as exc:
            self.report.status = "failed"
            self.report.reason = (
                self.redact(str(exc))
                if isinstance(exc, DevPilotError)
                else (
                    f"Internal error ({type(exc).__name__}). "
                    "Check the setup and run the test suite."
                )
            )
        finally:
            stopped.set()
            sweeper.join(timeout=1)
            self.report.finished_at = datetime.now(UTC)
        return self.report

    @staticmethod
    def next_node(node: str, state: AgentState) -> str:
        if node == "validate_patch":
            return "recover" if state.get("feedback") else "test"
        if node == "test":
            return "review" if state["test_result"].passed else "recover"
        if node == "recover":
            return END if state["status"] == "failed" else "patch"
        return {
            "clone": "baseline",
            "baseline": "locate",
            "locate": "diagnose",
            "diagnose": "patch",
            "patch": "validate_patch",
            "review": END,
        }[node]

    def clone(self, state: AgentState) -> dict[str, Any]:
        self.cloner.timeout = min(self.cloner.timeout, self.remaining())
        self.report.commit_sha = self.cloner.clone(state["repo_url"], Path(state["workdir"]))
        check_python_project(Path(state["workdir"]))
        return {}

    def run_tests(self, state: AgentState) -> TestResult:
        if hasattr(self.sandbox, "job_id"):
            slot = (
                f"test-{state['attempts']}"
                if state.get("attempts")
                else f"baseline-{len(self.report.baseline_results) + 1}"
            )
            self.sandbox.job_id = f"{self.report.id}-{slot}"
        result = self.sandbox.run(Path(state["workdir"]), timeout=self.remaining())
        result.output_tail = self.redact(result.output_tail)
        result.infrastructure_error = self.redact(result.infrastructure_error)
        result.failure_details = {
            self.redact(k): self.redact(v) for k, v in result.failure_details.items()
        }
        result.outcomes = {self.redact(k): v for k, v in result.outcomes.items()}
        self.remaining()
        return result

    def baseline(self, state: AgentState) -> dict[str, Any]:
        results = []
        for number in range(1, 3):
            self.emit("baseline", "waiting", f"Running baseline {number}/2 in a fresh sandbox.")
            results.append(self.run_tests(state))
            self.report.baseline_results = list(results)
            self.report.baseline_result = results[0]
        for result in results:
            if result.timed_out:
                raise UnsuitableRepository("Baseline timed out within the sandbox's test limit.")
            if result.infrastructure_error or result.exit_code not in {0, 1}:
                raise UnsuitableRepository(
                    result.infrastructure_error
                    or "Baseline could not run pytest. Inspect its logs and dependencies."
                )
        if results[0].signature() != results[1].signature():
            raise UnsuitableRepository(
                "Baseline outcomes differ across two fresh sandboxes (possible flaky tests)."
            )
        result = results[0]
        if result.passed:
            raise UnsuitableRepository(
                "The suite already passes. Add a failing regression test before running DevPilot."
            )
        if not result.failures:
            raise UnsuitableRepository("No reproducible failing pytest test was found.")
        if self.expected_failures and set(result.failures) != self.expected_failures:
            raise UnsuitableRepository(
                "Baseline failures do not match --expected-failure. "
                "Resolve unrelated failures first. " + ", ".join(result.failures)
            )
        return {"baseline_result": result}

    def locate(self, state: AgentState) -> dict[str, Any]:
        names, context = locate(
            Path(state["workdir"]),
            state["issue_text"],
            state["baseline_result"].output_tail,
            self.redact,
        )
        self.report.relevant_files = names
        return {"relevant_files": names, "context": context}

    def diagnose(self, state: AgentState) -> dict[str, Any]:
        prompt = (
            'Return ONLY JSON: {"related":true,"hypothesis":"brief cause, fix and uncertainty"}. '
            "Set related false when the failures appear unrelated to the issue.\n"
            + self.evidence(state)
        )
        raw = self.llm.complete(SYSTEM, prompt, self.deadline)
        try:
            diagnosis = json.loads(raw)
            if not isinstance(diagnosis, dict) or not isinstance(diagnosis.get("hypothesis"), str):
                raise ValueError("invalid diagnosis")
            if diagnosis.get("related") is not True:
                raise UnsuitableRepository(
                    "The diagnosis could not link the baseline failures to the bug."
                )
            self.report.hypothesis = self.redact(diagnosis["hypothesis"][:6000])
        except (ValueError, KeyError, TypeError) as exc:
            raise DevPilotError(
                "Groq returned an invalid diagnosis. Retry with a clearer bug description."
            ) from exc
        return {"hypothesis": self.report.hypothesis}

    def evidence(self, state: AgentState) -> str:
        return json.dumps(
            {
                "issue": state["issue_text"],
                "original_source": state["context"],
                "baseline_failures": state["baseline_result"].failures,
                "baseline_output": failing_output(state["baseline_result"].output_tail),
            }
        )

    def patch(self, state: AgentState) -> dict[str, Any]:
        reset_to_baseline(Path(state["workdir"]))
        number = state.get("attempts", 0) + 1
        raw = self.llm.complete(
            SYSTEM + "\n" + PATCH,
            self.evidence(state)
            + "\n"
            + json.dumps(
                {
                    "hypothesis": state["hypothesis"],
                    "attempt": number,
                    "previous_feedback": state.get("feedback", ""),
                    "previous_patch": self.report.attempts[-1].patch
                    if self.report.attempts
                    else "",
                }
            ),
            self.deadline,
        )
        self.report.attempts.append(Attempt(attempt_no=number, patch=self.redact(raw)))
        return {"patch": raw, "attempts": number, "feedback": ""}

    def validate_patch(self, state: AgentState) -> dict[str, Any]:
        try:
            proposal = PatchProposal.model_validate_json(state["patch"])
            diff = self.validator.apply(Path(state["workdir"]), proposal)
            self.report.attempts[-1].patch = diff
            return {"patch": diff, "feedback": ""}
        except (PatchRejected, ValidationError) as exc:
            message = (
                str(exc)
                if isinstance(exc, PatchRejected)
                else "Invalid search/replace JSON schema."
            )
            self.report.attempts[-1].validation_error = self.redact(message)
            return {"feedback": message}

    def test(self, state: AgentState) -> dict[str, Any]:
        result = self.run_tests(state)
        baseline = state["baseline_result"]
        if result.passed:
            # A patch must not make tests disappear or turn failures/passes into skips.
            expected = {name for name, outcome in baseline.outcomes.items() if outcome != "skipped"}
            if set(result.outcomes) != set(baseline.outcomes) or any(
                result.outcomes.get(name) != "passed" for name in expected
            ):
                result.exit_code = 1
                result.infrastructure_error = (
                    "Test inventory changed or a previously executed test was skipped."
                )
        self.report.attempts[-1].test_result = result
        if result.timed_out:
            raise RunTimeout("Patched test run hit its hard sandbox timeout; retries stopped.")
        if result.infrastructure_error:
            raise DevPilotError(result.infrastructure_error)
        return {"test_result": result, "feedback": failing_output(result.output_tail)}

    def recover(self, state: AgentState) -> dict[str, Any]:
        reason = ""
        if state["attempts"] >= self.settings.max_attempts:
            reason = f"Stopped after {self.settings.max_attempts} patch attempts."
        if len(self.report.attempts) >= 2:
            previous, current = self.report.attempts[-2:]
            if current.validation_error and current.validation_error == previous.validation_error:
                reason = "The same patch validation error repeated twice."
            elif (
                current.test_result
                and previous.test_result
                and current.test_result.signature() == previous.test_result.signature()
            ):
                reason = "The same failing test outcomes repeated twice; no further retry was made."
        if reason:
            self.report.status, self.report.reason = "failed", reason
            return {"status": "failed"}
        self.emit(
            "recover",
            "waiting",
            "Retrying from the original baseline with failure feedback.",
            next_attempt=state["attempts"] + 1,
        )
        return {"status": "running"}

    def review(self, state: AgentState) -> dict[str, Any]:
        self.report.final_diff = state["patch"]
        raw = self.llm.complete(
            SYSTEM,
            "Review this validated diff. Briefly explain what changed, why, "
            "test evidence and risks. "
            "Be explicit that passing tests do not prove correctness. No confidence percentages.\n"
            + json.dumps(
                {
                    "issue": state["issue_text"],
                    "hypothesis": state["hypothesis"],
                    "diff": state["patch"],
                    "test_result": state["test_result"].model_dump(),
                }
            ),
            self.deadline,
        )
        self.report.review = self.redact(raw[:12000])
        if self.on_review:
            workdir = Path(state["workdir"])
            paths = set(re.findall(r"^\+\+\+ b/(.+)$", state["patch"], re.MULTILINE))
            files = {name: (workdir / name).read_text() for name in paths}
            if any(self.redact.contains_secret(content) for content in files.values()):
                raise DevPilotError(
                    "Source snapshot contains secret-like content; publication blocked."
                )
            self.on_review(self.report, files)
        self.report.status = "ready_for_review"
        self.report.reason = (
            "Patch and test evidence exported for human review. Nothing was pushed."
        )
        return {"status": "ready_for_review"}
