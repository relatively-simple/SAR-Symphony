"""SSE streaming discovery endpoint for custom sky coordinates."""

import json
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse

from app.config import Settings, get_settings
from app.pipeline.run import run_explore_pipeline


router = APIRouter(prefix="/api", tags=["explore"])


@router.get("/explore")
async def explore_sky(
    ra: str = Query(..., description="Right Ascension (decimal deg or HMS like 08h55m10.8s)"),
    dec: str = Query("", description="Declination (decimal deg or DMS; optional if combined in ra)"),
    fov: float = Query(0.05, description="Field of view in degrees (0.05, 0.1, or 0.25)"),
    preset: str | None = Query(None, description="Optional preset slug for fast lookup"),
    settings: Settings = Depends(get_settings),
) -> StreamingResponse:
    """Stream Server-Sent ProgressEvents ending in `done` with `session_id`."""

    async def event_stream():
        async for ev in run_explore_pipeline(ra, dec, fov, settings, preset_slug=preset):
            payload = ev.model_dump_json()
            yield f"event: {ev.stage}\ndata: {payload}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
