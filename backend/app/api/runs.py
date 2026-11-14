import re

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select

from app.db.models import RunRow
from app.deps import DB, require_access
from app.errors import DevPilotError
from app.github.clone import validate_repo_url
from app.service import serialize_run

router = APIRouter(prefix="/api/runs", dependencies=[Depends(require_access)])


class NewRun(BaseModel):
    repo_url: str = Field(max_length=500)
    issue_text: str = Field(min_length=8, max_length=16000)
    dry_run: bool = True
    expected_failures: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("repo_url")
    @classmethod
    def github_only(cls, value: str) -> str:
        try:
            return validate_repo_url(value.rstrip("/"))
        except DevPilotError as exc:
            raise ValueError(str(exc)) from exc


class Approval(BaseModel):
    diff_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


@router.get("")
def list_runs(db: DB, limit: int = 100) -> list[dict]:
    rows = db.scalars(
        select(RunRow).order_by(RunRow.created_at.desc()).limit(max(1, min(limit, 200)))
    )
    return [serialize_run(row, db, False) for row in rows]


@router.post("", status_code=202)
def create_run(body: NewRun, request: Request, db: DB) -> dict:
    try:
        # Preflight before inserting a run; unavailable workers never simulate success.
        service = request.app.state.service
        if not service.settings.groq_api_key.get_secret_value():
            raise HTTPException(503, "Set GROQ_API_KEY on the worker before starting live runs.")
        request_id = request.headers.get("Idempotency-Key", "")
        if request_id and not re.fullmatch(r"[a-f0-9]{32}", request_id):
            raise HTTPException(400, "Use a 32-character hexadecimal Idempotency-Key.")
        run_id = service.create(
            body.repo_url, body.issue_text, body.dry_run, body.expected_failures, request_id
        )
    except DevPilotError as exc:
        raise HTTPException(409, str(exc)) from exc
    row = db.get(RunRow, run_id)
    assert row is not None
    return serialize_run(row, db)


@router.get("/{run_id}")
def get_run(run_id: str, db: DB) -> dict:
    row = db.get(RunRow, run_id)
    if row is None:
        raise HTTPException(404, "Run not found on this worker.")
    return serialize_run(row, db)


@router.get("/{run_id}/report")
def report(run_id: str, db: DB) -> JSONResponse:
    row = db.get(RunRow, run_id)
    if row is None:
        raise HTTPException(404, "Run not found.")
    record = serialize_run(row, db)
    decisions = [e for e in record["events"] if e["node"] == "approval" and e["type"] == "end"]
    record["approval_record"]["events"] = decisions
    safe_id = re.sub(r"[^A-Za-z0-9-]", "_", run_id)
    return JSONResponse(
        {"schema_version": 1, **record},
        headers={"Content-Disposition": f'attachment; filename="devpilot-{safe_id}.json"'},
    )


def decide(run_id: str, action: str, request: Request, digest: str = "") -> dict:
    try:
        request.app.state.service.decide(run_id, action, digest)
        return {"ok": True, "decision": action}
    except KeyError as exc:
        raise HTTPException(404, "Run not found.") from exc
    except DevPilotError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.post("/{run_id}/approve")
def approve(run_id: str, body: Approval, request: Request) -> dict:
    return decide(run_id, "approve", request, body.diff_sha256)


@router.post("/{run_id}/reject")
def reject(run_id: str, request: Request) -> dict:
    return decide(run_id, "reject", request)


@router.post("/{run_id}/cancel")
def cancel(run_id: str, request: Request) -> dict:
    return decide(run_id, "cancel", request)
