import asyncio
import json
import time
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select

from app.db.models import RunEventRow, RunRow
from app.deps import require_access
from app.service import ACTIVE, serialize_event

router = APIRouter(dependencies=[Depends(require_access)])


@router.get("/api/runs/{run_id}/events")
async def events(run_id: str, request: Request) -> StreamingResponse:
    with request.app.state.sessions() as db:
        if db.get(RunRow, run_id) is None:
            raise HTTPException(404, "Run not found.")
    try:
        cursor = max(0, int(request.headers.get("Last-Event-ID", "0")))
    except ValueError as exc:
        raise HTTPException(400, "Last-Event-ID must be an integer.") from exc

    async def stream() -> AsyncIterator[str]:
        nonlocal cursor
        heartbeat = time.monotonic()
        while not await request.is_disconnected():
            with request.app.state.sessions() as db:
                rows = list(
                    db.scalars(
                        select(RunEventRow)
                        .where(
                            RunEventRow.run_id == run_id,
                            RunEventRow.id > cursor,
                        )
                        .order_by(RunEventRow.id)
                        .limit(200)
                    )
                )
                row = db.get(RunRow, run_id)
                active = row is not None and row.status in ACTIVE
            for event in rows:
                cursor = event.id
                yield f"id: {event.id}\nevent: step\ndata: {json.dumps(serialize_event(event))}\n\n"
            if not active and len(rows) < 200:
                yield 'event: settled\ndata: {"poll":true}\n\n'
                return
            if time.monotonic() - heartbeat >= 15:
                yield ": heartbeat\n\n"
                heartbeat = time.monotonic()
            await asyncio.sleep(0.5)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
