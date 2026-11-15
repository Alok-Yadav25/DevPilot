from fastapi import APIRouter, Depends
from sqlalchemy import select

from app.db.models import EvalCaseRow, EvalResultRow
from app.deps import DB, require_access

router = APIRouter(dependencies=[Depends(require_access)])


@router.get("/api/eval")
def evaluation(db: DB) -> dict:
    cases = list(db.scalars(select(EvalCaseRow).order_by(EvalCaseRow.id)))
    results = list(db.scalars(select(EvalResultRow).order_by(EvalResultRow.id)))
    latest = {r.case_id: r for r in results if r.evidence.get("source") == "real_api"}
    passed = sum(r.result == "passed" for r in latest.values())
    executed = len(latest)
    return {
        "total_cases": len(cases),
        "executed": executed,
        "passed": passed,
        "failed": executed - passed,
        "unverified_results": sum(r.evidence.get("source") != "real_api" for r in results),
        "repair_success": round(passed / executed * 100, 1) if executed else None,
        "success_rate": round(passed / executed * 100, 1) if executed else None,
        "average_attempts": round(sum(r.attempts for r in latest.values()) / executed, 2)
        if executed
        else None,
        "results": [
            {
                "id": c.id,
                "name": c.name,
                "repo": c.repo,
                "category": c.category,
                "status": latest[c.id].result if c.id in latest else "not_run",
                "attempts": latest[c.id].attempts if c.id in latest else 0,
                "failure_reason": latest[c.id].failure_reason if c.id in latest else "",
                "commit_sha": latest[c.id].commit_sha if c.id in latest else "",
                "model": latest[c.id].model if c.id in latest else "",
                "evidence": latest[c.id].evidence if c.id in latest else {},
                "duration_seconds": latest[c.id].duration_seconds if c.id in latest else None,
            }
            for c in cases
        ],
    }
