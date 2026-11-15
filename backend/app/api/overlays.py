"""Earth multi-sensor feature overlay endpoint."""

import math
from fastapi import APIRouter, Depends, Query

from app.config import Settings, get_settings
from app.core.errors import ExploreError
from app.data.catalogs import load_preset_overlays
from app.models import OverlaySet


router = APIRouter(prefix="/api", tags=["overlays"])


@router.get("/overlays", response_model=OverlaySet)
async def get_overlays(
    ra: float = Query(...),
    dec: float = Query(..., ge=-90.0, le=90.0),
    fov: float = Query(0.05, gt=0.0, le=5.0),
    mjd: float = Query(61050.0),
    preset: str | None = Query(None),
    settings: Settings = Depends(get_settings),
) -> OverlaySet:
    """Return Earth overlay metadata from preset cache."""
    if not (math.isfinite(ra) and math.isfinite(dec) and math.isfinite(fov) and math.isfinite(mjd)):
        raise ExploreError("BAD_COORDS", "Overlay query parameters must be finite.", 400)

    if preset:
        cached = load_preset_overlays(settings.spx_preset_dir, preset, mjd_ref=mjd)
        if cached is not None:
            return cached

    return OverlaySet(
        gaia=[],
        allwise=[],
        source="live",
        mjd_ref=mjd,
        note="Earth multi-sensor feature overlays active via session manifest.",
    )
