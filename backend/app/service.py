"""A bounded single-process worker with durable run/event records.

Use one Uvicorn worker. A process lock prevents two app processes sharing the DB
from executing against the same local sandbox host. Restarted jobs are failed
explicitly; they are never silently resumed or published.
"""

import hashlib
import json
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.agent.graph import Agent
from app.agent.llm import GroqClient
from app.agent.state import Event, RunReport
from app.config import Settings
from app.db.models import AttemptRow, RunEventRow, RunRow
from app.errors import DevPilotError
from app.github.client import GitHubClient
from app.github.pr import publish_reviewed_patch
from app.sandbox.factory import make_runner
from app.security import Redactor

ACTIVE = {"queued", "running", "publishing"}


def utc_iso(value: datetime) -> str:
    return value.replace(tzinfo=UTC).isoformat() if value.tzinfo is None else value.isoformat()


def serialize_event(event: RunEventRow) -> dict[str, Any]:
    return {
        "id": event.id,
        "timestamp": utc_iso(event.created_at),
        "node": event.node,
        "type": event.type,
        "message": event.message,
        "payload": event.payload,
    }


def serialize_run(row: RunRow, session: Session, detail: bool = True) -> dict[str, Any]:
    report = dict(row.report or {})
    report.update(
        id=row.id,
        repo_url=row.repo_url,
        issue_text=row.issue_text,
        status=row.status,
        created_at=utc_iso(row.created_at),
        finished_at=utc_iso(row.finished_at) if row.finished_at else None,
        final_diff=row.final_diff,
        pr_url=row.pr_url,
        dry_run=row.dry_run,
        mode="live",
    )
    for key, default in {
        "attempts": [],
        "events": [],
        "reason": "",
        "review": "",
        "hypothesis": "",
        "relevant_files": [],
    }.items():
        report.setdefault(key, default)
    if detail:
        report["events"] = [
            serialize_event(e)
            for e in session.scalars(
                select(RunEventRow).where(RunEventRow.run_id == row.id).order_by(RunEventRow.id)
            )
        ]
    else:
        report["events"] = []
    return report


class RunService:
    def __init__(self, settings: Settings, sessions: sessionmaker[Session]) -> None:
        self.settings = settings
        self.sessions = sessions
        self.redact = Redactor(settings.secrets())
        self.executor = ThreadPoolExecutor(
            max_workers=settings.max_concurrent_runs, thread_name_prefix="devpilot"
        )
        self.lock = threading.RLock()
        self.cancellations: dict[str, threading.Event] = {}
        self.limits: dict[str, dict[str, str]] = {"groq": {}, "github": {}}

    def recover_interrupted(self) -> None:
        with self.sessions.begin() as session:
            for row in session.scalars(select(RunRow).where(RunRow.status.in_(ACTIVE))):
                was_publishing = row.status == "publishing"
                row.status = "failed"
                row.finished_at = datetime.now(UTC)
                row.report = {
                    **row.report,
                    "reason": (
                        "Worker restarted during publication. Inspect GitHub for the run branch/PR "
                        "before taking any further action."
                        if was_publishing
                        else "Worker restarted. This run was stopped; start a new run to retry."
                    ),
                }

    def add_event(self, run_id: str, event: Event) -> None:
        safe = Event.model_validate_json(self.redact(event.model_dump_json()))
        with self.sessions.begin() as session:
            session.add(
                RunEventRow(
                    run_id=run_id,
                    node=safe.node,
                    type=safe.type,
                    message=safe.message,
                    payload=safe.payload,
                    created_at=safe.timestamp,
                )
            )
            row = session.get(RunRow, run_id)
            if row and safe.payload:
                report = dict(row.report)
                for key in ("hypothesis", "relevant_files", "baseline_result"):
                    if key in safe.payload:
                        report[key] = safe.payload[key]
                attempts = list(report.get("attempts", []))
                if safe.node == "patch" and safe.type == "end":
                    number = int(safe.payload.get("attempts", 0))
                    if number > len(attempts):
                        attempts.append({"attempt_no": number, "patch": "", "test_result": None})
                    row.attempts = number
                    row.final_diff = ""
                if safe.node == "validate_patch" and not safe.payload.get("feedback"):
                    diff = safe.payload.get("patch")
                    if isinstance(diff, str) and diff.startswith("--- a/"):
                        row.final_diff = diff
                        if attempts:
                            attempts[-1] = {**attempts[-1], "patch": diff}
                if "test_result" in safe.payload and attempts:
                    attempts[-1] = {**attempts[-1], "test_result": safe.payload["test_result"]}
                report["attempts"] = attempts
                row.report = report

    def create(self, repo: str, issue: str, dry: bool, expected: list[str]) -> str:
        with self.lock, self.sessions.begin() as session:
            active = len(list(session.scalars(select(RunRow.id).where(RunRow.status.in_(ACTIVE)))))
            if active >= self.settings.max_concurrent_runs + self.settings.max_queued_runs:
                raise DevPilotError("The run queue is full. Wait and retry.")
            run_id = uuid4().hex[:12]
            session.add(
                RunRow(
                    id=run_id,
                    repo_url=repo,
                    issue_text=self.redact(issue),
                    dry_run=dry,
                    expected_failures=expected,
                    status="queued",
                    report={},
                )
            )
        cancellation = threading.Event()
        with self.lock:
            self.cancellations[run_id] = cancellation
        self.executor.submit(self.execute, run_id, cancellation)
        return run_id

    def execute(self, run_id: str, cancel: threading.Event) -> None:
        llm = None
        sandbox = None
        try:
            with self.sessions.begin() as session:
                row = session.get(RunRow, run_id)
                if row is None:
                    return
                repo, issue, expected = row.repo_url, row.issue_text, row.expected_failures
                row.status = "running"
            sandbox = make_runner(
                self.settings,
                lambda message: self.add_event(
                    run_id, Event(node="sandbox", type="waiting", message=message)
                ),
                cancel,
            )
            sandbox.preflight()
            key = self.settings.groq_api_key.get_secret_value()
            if not key:
                raise DevPilotError("GROQ_API_KEY is missing on the worker.")
            llm = GroqClient(
                key,
                self.settings.groq_model,
                lambda msg: self.add_event(run_id, Event(node="llm", type="waiting", message=msg)),
                cancel=cancel,
            )
            llm.preflight()

            def snapshot(report: RunReport, files: dict[str, str]) -> None:
                with self.sessions.begin() as session:
                    row = session.get(RunRow, run_id)
                    if row:
                        row.source_snapshot = files

            agent = Agent(
                self.settings,
                llm,
                sandbox,
                on_event=lambda event: self.add_event(run_id, event),
                cancel=cancel,
                on_review=snapshot,
            )
            agent.report.id = run_id
            report = agent.run(repo, issue, expected)
            with self.sessions.begin() as session:
                row = session.get(RunRow, run_id)
                if row:
                    row.report = json.loads(self.redact(report.model_dump_json()))
                    row.final_diff = report.final_diff
                    row.status = report.status
                    row.attempts = len(report.attempts)
                    row.finished_at = report.finished_at
                    for attempt in report.attempts:
                        result = attempt.test_result
                        session.add(
                            AttemptRow(
                                run_id=run_id,
                                attempt_no=attempt.attempt_no,
                                patch=attempt.patch,
                                test_output_tail=result.output_tail if result else "",
                                passed=bool(result and result.passed),
                            )
                        )
            self.limits["groq"] = llm.limits
            if report.status == "ready_for_review":
                self.add_event(
                    run_id,
                    Event(
                        node="approval",
                        type="start",
                        message="Waiting for human review. No branch has been pushed.",
                    ),
                )
        except Exception as exc:
            reason = (
                self.redact(str(exc))
                if isinstance(exc, DevPilotError)
                else f"Worker error ({type(exc).__name__}). Check backend logs and setup."
            )
            with self.sessions.begin() as session:
                row = session.get(RunRow, run_id)
                if row:
                    row.status = "failed"
                    row.finished_at = datetime.now(UTC)
                    row.report = {**row.report, "reason": reason}
            self.add_event(run_id, Event(node="worker", type="error", message=reason))
        finally:
            if sandbox:
                self.limits["github"] = getattr(sandbox, "limits", {})
                sandbox.close()
            if llm:
                llm.close()
            with self.lock:
                self.cancellations.pop(run_id, None)

    def decide(self, run_id: str, action: str, digest: str = "") -> None:
        with self.lock, self.sessions.begin() as session:
            # Row-level lock serializes decisions on PostgreSQL, including multiple clients.
            row = session.scalar(select(RunRow).where(RunRow.id == run_id).with_for_update())
            if row is None:
                raise KeyError(run_id)
            if action == "cancel":
                if row.status not in {"queued", "running"}:
                    raise DevPilotError("This run is no longer cancellable.")
                cancel = self.cancellations.get(run_id)
                if cancel:
                    cancel.set()
                return
            if row.status != "ready_for_review":
                raise DevPilotError("Only a finished, reviewed patch can be approved or rejected.")
            if action == "reject":
                row.status = "rejected"
                row.source_snapshot = {}
                row.report = {
                    **row.report,
                    "reason": "Rejected by the operator. No changes published.",
                }
            elif action == "approve":
                actual = hashlib.sha256(row.final_diff.encode()).hexdigest()
                if not row.final_diff or not __import__("hmac").compare_digest(actual, digest):
                    raise DevPilotError("The reviewed diff changed. Reload it before approving.")
                if not row.dry_run and not self.settings.github_token.get_secret_value():
                    raise DevPilotError(
                        "Set a repository-scoped GITHUB_TOKEN on the worker before approval."
                    )
                row.approved_diff_sha256 = digest
                row.status = "completed" if row.dry_run else "publishing"
                row.report = {
                    **row.report,
                    "reason": "Human approval recorded for the exact tested diff.",
                }
            else:
                raise DevPilotError("Unsupported decision.")
        self.add_event(
            run_id, Event(node="approval", type="end", message=f"Operator chose {action}.")
        )
        if action == "approve":
            with self.sessions() as session:
                row = session.get(RunRow, run_id)
                should_publish = bool(row and row.status == "publishing")
            if should_publish:
                self.executor.submit(self.publish, run_id)

    def publish(self, run_id: str) -> None:
        github = GitHubClient(self.settings.github_token.get_secret_value())
        try:
            with self.sessions() as session:
                row = session.get(RunRow, run_id)
                if not row or row.status != "publishing" or not row.approved_diff_sha256:
                    return
                report = RunReport.model_validate(row.report)
                files, digest = row.source_snapshot, row.approved_diff_sha256
            self.add_event(
                run_id,
                Event(
                    node="open_pr",
                    type="start",
                    message="Publishing the human-approved patch to a new branch.",
                ),
            )
            url = publish_reviewed_patch(github, report, files, digest)
            with self.sessions.begin() as session:
                row = session.get(RunRow, run_id)
                if row:
                    row.pr_url, row.status = url, "pr_created"
                    row.source_snapshot = {}
                    row.report = {
                        **row.report,
                        "reason": "Draft pull request opened. Human review is still required.",
                    }
            self.add_event(
                run_id,
                Event(
                    node="open_pr",
                    type="end",
                    message="Draft pull request opened. Nothing merged.",
                    payload={"pr_url": url},
                ),
            )
        except Exception as exc:
            reason = (
                self.redact(str(exc))
                if isinstance(exc, DevPilotError)
                else "Publication failed. Inspect GitHub for the run branch before retrying."
            )
            with self.sessions.begin() as session:
                row = session.get(RunRow, run_id)
                if row:
                    row.status = "failed"
                    row.report = {
                        **row.report,
                        "reason": reason
                        + " A branch may already exist; no automatic replay is attempted.",
                    }
            self.add_event(run_id, Event(node="open_pr", type="error", message=reason))
        finally:
            self.limits["github"] = github.limits
            github.close()

    def shutdown(self) -> None:
        for cancellation in self.cancellations.values():
            cancellation.set()
        self.executor.shutdown(wait=False, cancel_futures=True)
