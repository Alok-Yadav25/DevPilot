"""A bounded single-process worker with durable run/event records.

Database leases prevent duplicate ownership; checkpoints contain no local paths.
"""

import hashlib
import json
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from sqlalchemy import func, or_, select, text, update
from sqlalchemy.orm import Session, sessionmaker

from app.agent.graph import Agent
from app.agent.llm import GroqClient
from app.agent.state import Event, RunReport, TestResult
from app.config import Settings
from app.db.models import AttemptRow, ReplayRunRow, RunEventRow, RunRow
from app.errors import DevPilotError, RunCancelled, WorkerPaused
from app.github.client import GitHubClient
from app.github.pr import publish_reviewed_patch
from app.policy import RunPolicy
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
        approved=bool(row.approved_diff_sha256),
        approval_record={
            "diff_sha256": row.approved_diff_sha256,
            "approved": bool(row.approved_diff_sha256),
        },
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
    report["test_evidence"] = [
        {
            "job_id": job_id,
            "run_id": job["run_id"],
            "status": job.get("status", "unknown"),
            "url": f"https://github.com/{job['sandbox_repo']}/actions/runs/{job['run_id']}",
        }
        for job_id, job in (row.remote_jobs or {}).items()
        if job.get("run_id") and job.get("sandbox_repo")
    ]
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
        self.worker_id = uuid4().hex
        self.stopping = threading.Event()
        self.lock = threading.RLock()
        self.cancellations: dict[str, threading.Event] = {}
        self.limits: dict[str, dict[str, str]] = {"groq": {}, "github": {}}

    def claim(self, run_id: str) -> bool:
        with self.sessions.begin() as db:
            if db.bind is not None and db.bind.dialect.name == "postgresql":
                db.execute(text("SELECT pg_advisory_xact_lock(73486021)"))
            else:
                db.execute(text("BEGIN IMMEDIATE"))
            current = (
                db.scalar(
                    select(func.count())
                    .select_from(RunRow)
                    .where(RunRow.status.in_(ACTIVE), RunRow.lease_expires_at > datetime.now(UTC))
                )
                or 0
            )
            if current >= self.settings.max_concurrent_runs:
                return False
            result = db.execute(
                update(RunRow)
                .where(
                    RunRow.id == run_id,
                    RunRow.status.in_(ACTIVE),
                    or_(
                        RunRow.lease_expires_at.is_(None),
                        RunRow.lease_expires_at < datetime.now(UTC),
                    ),
                )
                .values(
                    worker_id=self.worker_id,
                    lease_expires_at=datetime.now(UTC) + timedelta(seconds=45),
                )
            )
            return bool(result.rowcount)  # type: ignore[attr-defined]

    def recover_interrupted(self) -> None:
        if self.stopping.is_set():
            return
        with self.sessions() as db:
            pending = list(
                db.scalars(
                    select(RunRow.id)
                    .where(
                        RunRow.status.in_(ACTIVE),
                        or_(
                            RunRow.lease_expires_at.is_(None),
                            RunRow.lease_expires_at < datetime.now(UTC),
                        ),
                    )
                    .order_by(RunRow.created_at)
                )
            )
        for run_id in pending:
            with self.sessions.begin() as db:
                row = db.get(RunRow, run_id)
                if row and row.status != "publishing" and row.checkpoint.get("node") == "review":
                    row.status = "ready_for_review"
                    row.report = row.checkpoint["report"]
                    row.final_diff = row.report["final_diff"]
                    row.worker_id, row.lease_expires_at = None, None
                    continue
            with self.lock:
                if run_id in self.cancellations:
                    continue
                cancel = threading.Event()
                self.cancellations[run_id] = cancel
            self.executor.submit(self.execute, run_id, cancel)

    def heartbeat(self, run_id: str, cancel: threading.Event, done: threading.Event) -> None:
        while not done.wait(10):
            try:
                with self.sessions.begin() as db:
                    row = db.get(RunRow, run_id)
                    if not row or row.worker_id != self.worker_id:
                        self.stopping.set()
                        return
                    if row.cancel_requested:
                        cancel.set()
                    row.lease_expires_at = datetime.now(UTC) + timedelta(seconds=45)
            except Exception:
                self.stopping.set()  # Pause on loss of lease storage; do not cancel a remote job.
                return

    def checkpoint(self, run_id: str, node: str, state: dict, report: RunReport) -> None:
        data = {
            k: v.model_dump(mode="json") if hasattr(v, "model_dump") else v
            for k, v in state.items()
            if k != "workdir"
        }
        safe = json.loads(
            self.redact(
                json.dumps({"node": node, "state": data, "report": report.model_dump(mode="json")})
            )
        )
        with self.sessions.begin() as db:
            row = db.scalar(select(RunRow).where(RunRow.id == run_id).with_for_update())
            if not row or row.worker_id != self.worker_id:
                raise WorkerPaused("Worker lease lost.")
            if row.cancel_requested:
                raise RunCancelled("Run cancelled.")
            row.checkpoint = safe
            row.report = safe["report"]
            row.final_diff = report.final_diff
            row.attempts = len(report.attempts)

    def save_job(self, run_id: str, job_id: str, job: dict) -> None:
        with self.sessions.begin() as db:
            row = db.scalar(select(RunRow).where(RunRow.id == run_id).with_for_update())
            if not row or row.worker_id != self.worker_id:
                raise WorkerPaused("Worker no longer owns this run.")
            row.remote_jobs = {**row.remote_jobs, job_id: job}

    def cleanup_retained_jobs(self) -> None:
        if self.settings.runner_mode != "github_actions":
            return
        cutoff = datetime.now(UTC) - timedelta(seconds=self.settings.retention_seconds)
        with self.sessions() as db:
            rows = [
                (r.id, r.remote_jobs)
                for r in db.scalars(
                    select(RunRow).where(
                        RunRow.finished_at < cutoff,
                        ~RunRow.status.in_(ACTIVE | {"ready_for_review"}),
                    )
                )
                if any(j.get("branch_created") for j in r.remote_jobs.values())
            ]
        for run_id, jobs in rows:
            runner = make_runner(self.settings)
            try:
                runner.runner.jobs = jobs  # type: ignore[attr-defined]
                runner.cancel_pending()  # type: ignore[attr-defined]
                with self.sessions.begin() as db:
                    row = db.get(RunRow, run_id)
                    if row:
                        row.remote_jobs = {
                            key: {**job, "branch_created": False} for key, job in jobs.items()
                        }
            finally:
                runner.close()

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

    def create(
        self, repo: str, issue: str, dry: bool, expected: list[str], request_id: str = ""
    ) -> str:
        if self.settings.runner_mode == "replay":
            raise DevPilotError(
                "Live runs are disabled in replay mode. Choose a recording or sample."
            )
        if request_id:
            with self.sessions() as db:
                previous = db.get(RunRow, request_id)
                if previous:
                    if (
                        previous.repo_url != repo
                        or previous.issue_text != self.redact(issue)
                        or previous.dry_run != dry
                        or previous.expected_failures != expected
                    ):
                        raise DevPilotError(
                            "Idempotency key was already used for a different run request."
                        )
                    return previous.id
        repo = RunPolicy(self.settings).readiness(repo, issue)
        with self.lock, self.sessions.begin() as session:
            active = len(list(session.scalars(select(RunRow.id).where(RunRow.status.in_(ACTIVE)))))
            if active >= self.settings.max_concurrent_runs + self.settings.max_queued_runs:
                raise DevPilotError("The run queue is full. Wait and retry.")
            run_id = request_id or uuid4().hex[:12]
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
        heartbeat_done = threading.Event()
        owned = False
        try:
            owned = self.claim(run_id)
            if not owned:
                return
            threading.Thread(
                target=self.heartbeat, args=(run_id, cancel, heartbeat_done), daemon=True
            ).start()
            with self.sessions.begin() as session:
                row = session.get(RunRow, run_id)
                if row is None:
                    return
                repo, issue, expected = row.repo_url, row.issue_text, row.expected_failures
                resume, jobs = row.checkpoint, row.remote_jobs
                if row.cancel_requested:
                    cancel.set()
                publishing = row.status == "publishing"
                row.status = "publishing" if publishing else "running"
            if publishing:
                self.publish(run_id)
                return
            sandbox = make_runner(
                self.settings,
                lambda message: self.add_event(
                    run_id, Event(node="sandbox", type="waiting", message=message)
                ),
                cancel,
            )
            if hasattr(sandbox, "runner"):
                sandbox.runner.pause_requested = self.stopping
                sandbox.runner.jobs = jobs
                sandbox.runner.on_job = lambda job_id, job: self.save_job(run_id, job_id, job)
            if cancel.is_set():
                if hasattr(sandbox, "cancel_pending"):
                    sandbox.cancel_pending()
                raise RunCancelled("Cancelled by the operator; remote cleanup requested.")
            RunPolicy(self.settings).remote(repo, issue)
            sandbox.preflight()
            key = self.settings.groq_api_key.get_secret_value()
            if not key:
                raise DevPilotError("GROQ_API_KEY is missing on the worker.")

            def model_waiting(message: str) -> None:
                if llm:
                    self.limits["groq"] = dict(llm.limits)
                self.add_event(run_id, Event(node="llm", type="waiting", message=message))

            llm = GroqClient(
                key,
                self.settings.groq_model,
                model_waiting,
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
                on_checkpoint=lambda node, state, report: self.checkpoint(
                    run_id, node, state, report
                ),
            )
            agent.pause_requested = self.stopping
            agent.report.id = run_id
            report = agent.run(repo, issue, expected, resume=resume or None)
            with self.sessions.begin() as session:
                row = session.get(RunRow, run_id)
                if row and row.worker_id == self.worker_id:
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
                        message="Waiting for human review. No target branch has been pushed.",
                    ),
                )
                self.record_replay(run_id)
        except WorkerPaused:
            pass  # Leave status and remote jobs intact for recovery.
        except Exception as exc:
            reason = (
                self.redact(str(exc))
                if isinstance(exc, DevPilotError)
                else f"Worker error ({type(exc).__name__}). Check backend logs and setup."
            )
            with self.sessions.begin() as session:
                row = session.get(RunRow, run_id)
                if row and row.worker_id == self.worker_id:
                    row.status = "cancelled" if cancel.is_set() else "failed"
                    row.finished_at = datetime.now(UTC)
                    row.report = {**row.report, "reason": reason}
            self.add_event(run_id, Event(node="worker", type="error", message=reason))
        finally:
            heartbeat_done.set()
            if owned:
                with self.sessions.begin() as db:
                    db.execute(
                        update(RunRow)
                        .where(RunRow.id == run_id, RunRow.worker_id == self.worker_id)
                        .values(worker_id=None, lease_expires_at=None)
                    )
            if (
                owned
                and sandbox
                and not self.stopping.is_set()
                and hasattr(sandbox, "cancel_pending")
            ):
                with self.sessions() as db:
                    finished = db.get(RunRow, run_id)
                    needs_cleanup = bool(
                        finished
                        and finished.status in {"failed", "cancelled", "timeout", "unsuitable"}
                    )
                if needs_cleanup:
                    try:
                        sandbox.cancel_pending()
                    except DevPilotError as exc:
                        self.add_event(
                            run_id,
                            Event(node="sandbox", type="error", message=self.redact(str(exc))),
                        )
            if sandbox:
                self.limits["github"] = getattr(sandbox, "limits", {})
                sandbox.close()
            if llm:
                llm.close()
            with self.lock:
                self.cancellations.pop(run_id, None)

    def record_replay(self, run_id: str) -> None:
        if self.settings.runner_mode != "github_actions":
            return
        with self.sessions.begin() as db:
            row = db.get(RunRow, run_id)
            if (
                not row
                or row.status != "ready_for_review"
                or db.get(ReplayRunRow, run_id) is not None
            ):
                return
            record = serialize_run(row, db)
            attempts = record.get("attempts", [])
            if (
                not record.get("test_evidence")
                or not record.get("review")
                or not attempts
                or not attempts[-1].get("test_result")
                or not TestResult.model_validate(attempts[-1]["test_result"]).passed
            ):
                return
            db.add(
                ReplayRunRow(
                    id=run_id,
                    run_id=run_id,
                    repo_url=row.repo_url,
                    record=json.loads(self.redact(json.dumps(record))),
                )
            )

    def decide(self, run_id: str, action: str, digest: str = "") -> None:
        with self.lock, self.sessions.begin() as session:
            # Row-level lock serializes decisions on PostgreSQL, including multiple clients.
            row = session.scalar(select(RunRow).where(RunRow.id == run_id).with_for_update())
            if row is None:
                raise KeyError(run_id)
            if action == "cancel":
                if row.status == "cancelled":
                    return
                if row.status not in {"queued", "running"}:
                    raise DevPilotError("This run is no longer cancellable.")
                row.cancel_requested = True
                cancel = self.cancellations.get(run_id)
                if cancel:
                    cancel.set()
                if row.status == "queued":
                    row.status = "cancelled"
                    row.finished_at = datetime.now(UTC)
                return
            if action == "reject" and row.status == "rejected":
                return
            if (
                action == "approve"
                and row.status in {"completed", "publishing", "pr_created"}
                and row.approved_diff_sha256 == digest
            ):
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
                if not row.dry_run and not self.settings.target_github_token.get_secret_value():
                    raise DevPilotError(
                        "Set a repository-scoped TARGET_GITHUB_TOKEN on the worker before approval."
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
                self.recover_interrupted()

    def publish(self, run_id: str) -> None:
        github = GitHubClient(self.settings.target_github_token.get_secret_value())
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
        self.stopping.set()
        self.executor.shutdown(wait=False, cancel_futures=True)
