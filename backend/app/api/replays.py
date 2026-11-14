"""Read-only public recordings: no model, runner or GitHub request is made here."""

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.db.models import ReplayRunRow
from app.deps import DB
from app.sandbox.factory import ReplayRunner
from app.service import utc_iso

router = APIRouter(prefix="/api/replays")


@router.get("")
def recordings(db: DB) -> list[dict]:
    return [
        {
            "id": row.id,
            "repo_url": row.repo_url,
            "recorded_at": utc_iso(row.created_at),
            "label": "Recorded real run",
        }
        for row in db.scalars(
            select(ReplayRunRow).order_by(ReplayRunRow.created_at.desc()).limit(30)
        )
    ]


@router.get("/{record_id}")
def recording(record_id: str, db: DB) -> dict:
    row = db.get(ReplayRunRow, record_id)
    if not row:
        raise HTTPException(
            404, "No recording found. Choose a recorded run or an illustrative example."
        )
    return {**ReplayRunner().play(row.record), "recorded_at": utc_iso(row.created_at)}
