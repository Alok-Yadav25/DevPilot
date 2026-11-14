"""Durable node checkpoints, remote jobs and expiring worker leases."""

import sqlalchemy as sa
from alembic import op

revision = "0002_recovery"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("runs", sa.Column("checkpoint", sa.JSON(), nullable=False, server_default="{}"))
    op.add_column("runs", sa.Column("remote_jobs", sa.JSON(), nullable=False, server_default="{}"))
    op.add_column("runs", sa.Column("worker_id", sa.String(36)))
    op.add_column("runs", sa.Column("lease_expires_at", sa.DateTime(timezone=True)))
    op.add_column(
        "runs",
        sa.Column("cancel_requested", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    for name in ("cancel_requested", "lease_expires_at", "worker_id", "remote_jobs", "checkpoint"):
        op.drop_column("runs", name)
