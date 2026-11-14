"""Cross-mission Gaia DR3 and AllWISE catalog overlay endpoint."""

import json
import math
import os
from fastapi import APIRouter, Depends, Query

from app.config import Settings, get_settings
from app.core.errors import ExploreError
from app.data.catalogs import load_preset_overlays, query_live_overlays, repropagate_overlays
from app.data.http import create_async_client
from app.models import OverlaySet


router = APIRouter(prefix="/api", tags=["overlays"])


@router.get("/overlays", response_model=OverlaySet)
async def get_overlays(
    ra: float = Query(...),
    dec: float = Query(..., ge=-90.0, le=90.0),
    fov: float = Query(0.05, gt=0.0, le=1.0),
    mjd: float = Query(61050.0),
    preset: str | None = Query(None),
    settings: Settings = Depends(get_settings),
) -> OverlaySet:
    """Return Gaia DR3 PM vectors + AllWISE counterparts from preset/disk cache or live mirrors."""
    if not (math.isfinite(ra) and math.isfinite(dec) and math.isfinite(fov) and math.isfinite(mjd)):
        raise ExploreError("BAD_COORDS", "Overlay query parameters must be finite.", 400)
    ra_norm = ra % 360.0

    if preset:
        cached = load_preset_overlays(settings.spx_preset_dir, preset, mjd_ref=mjd)
        if cached is not None:
            return cached

    cache_dir = settings.spx_cache_dir / "overlays"
    cache_key = f"{ra_norm:.4f}_{dec:.4f}_{fov:.3f}.json"
    cache_path = cache_dir / cache_key
    if cache_path.exists():
        try:
            ov = OverlaySet.model_validate(json.loads(cache_path.read_text(encoding="utf-8")))
            if ov.source != "unavailable":
                return repropagate_overlays(ov, mjd)
        except Exception:
            pass

    async with create_async_client(timeout_s=15.0) as client:
        ov = await query_live_overlays(client, ra_norm, dec, fov, mjd)

    if ov.source == "live":
        try:
            cache_dir.mkdir(parents=True, exist_ok=True)
            tmp = cache_path.with_suffix(".tmp.json")
            tmp.write_text(ov.model_dump_json(), encoding="utf-8")
            os.replace(tmp, cache_path)
        except OSError:
            pass

    return ov
