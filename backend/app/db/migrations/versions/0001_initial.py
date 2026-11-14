"""Initial run, event, attempt and evaluation storage."""

import sqlalchemy as sa
from alembic import op

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("repo_url", sa.String(500), nullable=False),
        sa.Column("issue_text", sa.Text(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("pr_url", sa.String(500)),
        sa.Column("final_diff", sa.Text(), nullable=False),
        sa.Column("dry_run", sa.Boolean(), nullable=False),
        sa.Column("expected_failures", sa.JSON(), nullable=False),
        sa.Column("report", sa.JSON(), nullable=False),
        sa.Column("source_snapshot", sa.JSON(), nullable=False),
        sa.Column("approved_diff_sha256", sa.String(64)),
        sa.Column("publication", sa.JSON(), nullable=False),
    )
    op.create_index("ix_runs_status", "runs", ["status"])
    op.create_table(
        "run_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "run_id", sa.String(36), sa.ForeignKey("runs.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("node", sa.String(50), nullable=False),
        sa.Column("type", sa.String(20), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_run_events_run_id", "run_events", ["run_id"])
    op.create_table(
        "attempts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "run_id", sa.String(36), sa.ForeignKey("runs.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("attempt_no", sa.Integer(), nullable=False),
        sa.Column("patch", sa.Text(), nullable=False),
        sa.Column("test_output_tail", sa.Text(), nullable=False),
        sa.Column("passed", sa.Boolean(), nullable=False),
    )
    op.create_index("ix_attempts_run_id", "attempts", ["run_id"])
    op.create_table(
        "eval_cases",
        sa.Column("id", sa.String(50), primary_key=True),
        sa.Column("repo", sa.String(500), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("category", sa.String(100), nullable=False),
        sa.Column("bug_description", sa.Text(), nullable=False),
        sa.Column("expected_pass", sa.Boolean(), nullable=False),
    )
    op.create_table(
        "eval_results",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("case_id", sa.String(50), sa.ForeignKey("eval_cases.id"), nullable=False),
        sa.Column("run_id", sa.String(36), sa.ForeignKey("runs.id"), nullable=False),
        sa.Column("result", sa.String(20), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("duration_seconds", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_eval_results_case_id", "eval_results", ["case_id"])


def downgrade() -> None:
    for table in ("eval_results", "eval_cases", "attempts", "run_events", "runs"):
        op.drop_table(table)
