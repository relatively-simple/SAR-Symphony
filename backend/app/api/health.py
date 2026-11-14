"""Health check endpoint reporting IRSA status and cached presets."""

import time
from fastapi import APIRouter, Depends, Query

from app.config import Settings, get_settings
from app.data.http import create_async_client
from app.models import HealthStatus
from app.pipeline.session import list_ready_presets


router = APIRouter(prefix="/api", tags=["health"])

_IRSA_PING_TTL_S = 60.0
_last_irsa_check: tuple[float, bool] | None = None


@router.get("/health", response_model=HealthStatus)
async def health_check(
    live: bool = Query(False, description="Force live IRSA SIA ping bypassing 60s cache"),
    settings: Settings = Depends(get_settings),
) -> HealthStatus:
    """Verify server readiness, ready preset count, and optional cached IRSA ping."""
    global _last_irsa_check
    now = time.monotonic()
    if not live and _last_irsa_check is not None and (now - _last_irsa_check[0]) < _IRSA_PING_TTL_S:
        irsa_ok = _last_irsa_check[1]
    else:
        irsa_ok = False
        try:
            async with create_async_client(timeout_s=3.0) as client:
                r = await client.get(
                    "https://irsa.ipac.caltech.edu/SIA",
                    params={"COLLECTION": "spherex_dr1", "POS": "CIRCLE 269.45 4.77 0.01", "MAXREC": "1"},
                )
                irsa_ok = r.status_code < 500
        except Exception:
            irsa_ok = False
        _last_irsa_check = (now, irsa_ok)

    sessions_dir = settings.spx_cache_dir / "sessions"
    cache_entries = sum(1 for p in sessions_dir.iterdir() if p.is_dir()) if sessions_dir.exists() else 0

    return HealthStatus(
        irsa_ok=irsa_ok,
        cache_entries=cache_entries,
        presets_ready=list_ready_presets(settings.spx_preset_dir),
        version=settings.app_version,
    )
