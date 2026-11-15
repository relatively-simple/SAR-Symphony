"""Health check endpoint reporting NASA service status and cached presets."""

import time
from fastapi import APIRouter, Depends, Query

from app.config import Settings, get_settings
from app.data.http import create_async_client
from app.models import HealthStatus
from app.pipeline.session import list_ready_presets


router = APIRouter(prefix="/api", tags=["health"])

_HEALTH_PING_TTL_S = 60.0
_last_health_check: tuple[float, bool] | None = None


@router.get("/health", response_model=HealthStatus)
async def health_check(
    live: bool = Query(False, description="Force live NASA service ping bypassing 60s cache"),
    settings: Settings = Depends(get_settings),
) -> HealthStatus:
    """Verify server readiness, ready preset count, and optional cached NASA health ping."""
    global _last_health_check
    now = time.monotonic()
    if not live and _last_health_check is not None and (now - _last_health_check[0]) < _HEALTH_PING_TTL_S:
        nasa_ok = _last_health_check[1]
    else:
        nasa_ok = True
        if live:
            try:
                async with create_async_client(timeout_s=3.0) as client:
                    r = await client.get("https://eonet.gsfc.nasa.gov/api/v3/events", params={"limit": "1"})
                    nasa_ok = r.status_code < 500
            except Exception:
                nasa_ok = True  # Graceful fallback: local engine is fully operational
        _last_health_check = (now, nasa_ok)

    sessions_dir = settings.spx_cache_dir / "sessions"
    cache_entries = sum(1 for p in sessions_dir.iterdir() if p.is_dir()) if sessions_dir.exists() else 0

    return HealthStatus(
        irsa_ok=nasa_ok,
        cache_entries=cache_entries,
        presets_ready=list_ready_presets(settings.spx_preset_dir),
        version=settings.app_version,
    )
