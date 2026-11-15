"""Keep real evaluation provenance and failure reasons; do not invent old evidence."""

import sqlalchemy as sa
from alembic import op

revision = "0004_eval_evidence"
down_revision = "0003_replays"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for name, kind, default in (
        ("failure_reason", sa.Text(), ""),
        ("commit_sha", sa.String(40), ""),
        ("model", sa.String(200), ""),
        ("evidence", sa.JSON(), "{}"),
    ):
        op.add_column("eval_results", sa.Column(name, kind, nullable=False, server_default=default))


def downgrade() -> None:
    for name in ("evidence", "model", "commit_sha", "failure_reason"):
        op.drop_column("eval_results", name)
