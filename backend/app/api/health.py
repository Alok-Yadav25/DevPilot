from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select, text

from app.db.models import RunRow
from app.deps import require_access
from app.sandbox.factory import make_runner

router = APIRouter()


@router.get("/api/health")
def health(request: Request) -> dict:
    settings = request.app.state.settings
    database = False
    try:
        with request.app.state.engine.connect() as conn:
            conn.execute(text("SELECT 1 FROM runs LIMIT 1"))
            database = True
    except Exception:
        pass
    runner_healthy, runner_error, runner = False, "", None
    try:
        runner = make_runner(settings)
        runner.preflight()
        runner_healthy = True
        request.app.state.service.limits["github"].update(getattr(runner, "limits", {}))
    except Exception as exc:
        runner_error = request.app.state.service.redact(str(exc))
    finally:
        if runner:
            runner.close()
    groq = bool(settings.groq_api_key.get_secret_value())
    auth = bool(settings.api_access_token.get_secret_value())
    ready = database and runner_healthy and (groq or settings.runner_mode == "replay") and auth
    return {
        "status": "ready" if ready else "setup_required",
        "database": database,
        "runner": settings.runner_mode,
        "runner_healthy": runner_healthy,
        "runner_error": runner_error,
        "groq_configured": groq,
        "github_configured": bool(settings.target_github_token.get_secret_value()),
        "ready": ready,
        "model": settings.groq_model,
        "message": "Runner ready."
        if ready
        else "Check the selected runner, database, GROQ_API_KEY and API_ACCESS_TOKEN. "
        + runner_error,
    }


@router.get("/api/limits", dependencies=[Depends(require_access)])
def limits(request: Request) -> dict:
    service = request.app.state.service
    with service.sessions() as db:
        queued = db.scalar(
            select(func.count()).select_from(RunRow).where(RunRow.status == "queued")
        )
        active = db.scalar(
            select(func.count())
            .select_from(RunRow)
            .where(RunRow.status.in_({"running", "publishing"}))
        )
    remote_queue = None
    if service.settings.runner_mode == "github_actions":
        runner = None
        try:
            runner = make_runner(service.settings)
            remote_queue = runner.queued_jobs()  # type: ignore[attr-defined]
            service.limits["github"].update(getattr(runner, "limits", {}))
        except Exception:
            pass  # Unknown is honest when GitHub is unreachable or throttled.
        finally:
            if runner:
                runner.close()
    return {
        "runner": service.settings.runner_mode,
        "groq": service.limits["groq"] or None,
        "github": service.limits["github"] or None,
        "current_concurrent_runs": active,
        "queued_runs": queued,
        "github_queued_jobs": remote_queue,
        "max_concurrent_runs": service.settings.max_concurrent_runs,
        "max_attempts": service.settings.max_attempts,
        "test_timeout_seconds": service.settings.test_timeout_seconds,
        "note": "Budgets and remote queue counts are unknown until observed.",
    }
