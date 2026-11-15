"""Multi-sensor 6-signal Earth rhythm temporal spectrum endpoint."""

import math
from fastapi import APIRouter, Depends, Query

from app.config import Settings, get_settings
from app.core.errors import ExploreError
from app.models import SessionManifest, SpectrumResult
from app.pipeline.session import find_session_dir
from app.science.earth_signals import extract_signal_rhythm_at


router = APIRouter(prefix="/api/sessions", tags=["spectrum"])


@router.get("/{session_id}/spectrum", response_model=SpectrumResult)
def get_spectrum(
    session_id: str,
    ra: float = Query(..., description="Clicked longitude/RA in decimal degrees"),
    dec: float = Query(..., ge=-90.0, le=90.0, description="Clicked latitude/Dec in decimal degrees"),
    settings: Settings = Depends(get_settings),
) -> SpectrumResult:
    """Extract live 6-signal Earth rhythm (radar, rain, wind, temp, optical, nightlights) for clicked coordinates."""
    if not (math.isfinite(ra) and math.isfinite(dec)):
        raise ExploreError("BAD_COORDS", "Coordinates must be finite numbers.", 400)

    sdir = find_session_dir(settings, session_id)
    manifest_path = sdir / "manifest.json"

    if manifest_path.exists():
        manifest = SessionManifest.model_validate_json(manifest_path.read_text(encoding="utf-8"))
        return extract_signal_rhythm_at(lon=ra, lat=dec, session_dir=sdir, manifest=manifest)

    preset_spec_path = sdir / "spectrum.json"
    if preset_spec_path.exists():
        return SpectrumResult.model_validate_json(preset_spec_path.read_text(encoding="utf-8"))

    raise ExploreError("SPECTRUM_UNAVAILABLE", f"No manifest or spectrum available for session '{session_id}'.", 404)
