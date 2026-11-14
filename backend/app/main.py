import asyncio
import contextlib
import fcntl
import logging
import threading
import time
from collections import defaultdict, deque
from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import RequestResponseEndpoint
from starlette.responses import Response

from app.api import eval, events, health, repos, runs
from app.config import Settings
from app.db.models import Base
from app.db.session import make_engine, make_sessions
from app.github.clone import cleanup_stale
from app.logging import configure_redacted_logging
from app.security import Redactor
from app.service import RunService


def create_app(settings: Settings | None = None) -> FastAPI:
    config = settings or Settings()
    configure_redacted_logging(config.secrets())
    redact = Redactor(config.secrets())

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        config.work_root.mkdir(parents=True, exist_ok=True, mode=0o700)
        lease = (config.work_root / ".api-worker.lock").open("a")
        try:
            fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            lease.close()
            raise RuntimeError(
                "Run one API worker per sandbox host; another worker owns the lease."
            ) from None
        engine = make_engine(config)
        sessions = make_sessions(engine)
        app.state.settings, app.state.engine, app.state.sessions = config, engine, sessions
        service = RunService(config, sessions)
        app.state.service = service
        cleanup_stale(config.work_root)

        async def reap() -> None:
            while True:
                await asyncio.sleep(300)
                await asyncio.to_thread(cleanup_stale, config.work_root)

        reaper = asyncio.create_task(reap())
        try:
            if config.database_auto_create:
                Base.metadata.create_all(engine)
            service.recover_interrupted()
            from app.evaluation import seed_catalog

            with sessions.begin() as db:
                seed_catalog(db)
        except SQLAlchemyError:
            pass  # Health remains available with actionable setup status.
        try:
            yield
        finally:
            reaper.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await reaper
            service.shutdown()
            engine.dispose()
            fcntl.flock(lease, fcntl.LOCK_UN)
            lease.close()

    app = FastAPI(title="DevPilot", version="1.0.0", lifespan=lifespan)

    def safe_error(
        content: object, status: int, headers: Mapping[str, str] | None = None
    ) -> Response:
        # Encode first to cover nested Pydantic input/context and exception fields.
        def clean(value: Any) -> Any:
            if isinstance(value, str):
                return redact(value)
            if isinstance(value, dict):
                return {redact(str(k)): clean(v) for k, v in value.items()}
            if isinstance(value, list):
                return [clean(v) for v in value]
            return value

        return JSONResponse(
            clean(jsonable_encoder(content)),
            status_code=status,
            headers={k: redact(v) for k, v in (headers or {}).items()},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError) -> Response:
        return safe_error({"detail": exc.errors()}, 422)

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request: Request, exc: StarletteHTTPException) -> Response:
        return safe_error({"detail": exc.detail}, exc.status_code, exc.headers)

    @app.exception_handler(Exception)
    async def internal_error(request: Request, exc: Exception) -> JSONResponse:
        logging.getLogger("app").error(
            "Unhandled API error", exc_info=(type(exc), exc, exc.__traceback__)
        )
        return JSONResponse(
            {"detail": "Internal worker error. Check the redacted server logs."}, 500
        )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[x.strip() for x in config.cors_origins.split(",") if x.strip()],
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "Last-Event-ID"],
        expose_headers=["Retry-After"],
        allow_credentials=False,
    )
    hits: dict[str, deque[float]] = defaultdict(deque)
    lock = threading.Lock()

    @app.middleware("http")
    async def boundaries(request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.url.path.startswith("/api") and request.method != "OPTIONS":
            ip = request.client.host if request.client else "unknown"
            key = f"{ip}:{'write' if request.method == 'POST' else 'read'}"
            budget = config.requests_per_minute * (1 if request.method == "POST" else 10)
            now = time.monotonic()
            with lock:
                if len(hits) > 10000:
                    hits.clear()
                queue = hits[key]
                while queue and queue[0] < now - 60:
                    queue.popleft()
                if len(queue) >= budget:
                    return JSONResponse(
                        {"detail": "Too many requests. Wait one minute and retry."},
                        429,
                        headers={"Retry-After": "60"},
                    )
                queue.append(now)
            if request.method == "POST":
                body = bytearray()
                async for chunk in request.stream():
                    body.extend(chunk)
                    if len(body) > 64000:
                        return JSONResponse({"detail": "Request body exceeds 64 KB."}, 413)
                request._body = bytes(body)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

    @app.exception_handler(SQLAlchemyError)
    async def database_error(request: Request, exc: SQLAlchemyError) -> JSONResponse:
        return JSONResponse(
            {"detail": "Database unavailable. Start PostgreSQL and apply Alembic migrations."}, 503
        )

    for router in (health.router, runs.router, events.router, eval.router, repos.router):
        app.include_router(router)
    return app


app = create_app()
