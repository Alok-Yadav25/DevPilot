from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def now() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class RunRow(Base):
    __tablename__ = "runs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    repo_url: Mapped[str] = mapped_column(String(500))
    issue_text: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default="queued", index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    pr_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    final_diff: Mapped[str] = mapped_column(Text, default="")
    dry_run: Mapped[bool] = mapped_column(Boolean, default=True)
    expected_failures: Mapped[list[str]] = mapped_column(JSON, default=list)
    report: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    source_snapshot: Mapped[dict[str, str]] = mapped_column(JSON, default=dict)
    approved_diff_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    publication: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    checkpoint: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    remote_jobs: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    worker_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    cancel_requested: Mapped[bool] = mapped_column(Boolean, default=False)


class RunEventRow(Base):
    __tablename__ = "run_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), index=True)
    node: Mapped[str] = mapped_column(String(50))
    type: Mapped[str] = mapped_column(String(20))
    message: Mapped[str] = mapped_column(Text)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class AttemptRow(Base):
    __tablename__ = "attempts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), index=True)
    attempt_no: Mapped[int] = mapped_column(Integer)
    patch: Mapped[str] = mapped_column(Text)
    test_output_tail: Mapped[str] = mapped_column(Text, default="")
    passed: Mapped[bool] = mapped_column(Boolean, default=False)


class EvalCaseRow(Base):
    __tablename__ = "eval_cases"
    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    repo: Mapped[str] = mapped_column(String(500))
    name: Mapped[str] = mapped_column(String(200))
    category: Mapped[str] = mapped_column(String(100))
    bug_description: Mapped[str] = mapped_column(Text)
    expected_pass: Mapped[bool] = mapped_column(Boolean, default=True)


class EvalResultRow(Base):
    __tablename__ = "eval_results"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    case_id: Mapped[str] = mapped_column(ForeignKey("eval_cases.id"), index=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"))
    result: Mapped[str] = mapped_column(String(20))
    attempts: Mapped[int] = mapped_column(Integer)
    duration_seconds: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
