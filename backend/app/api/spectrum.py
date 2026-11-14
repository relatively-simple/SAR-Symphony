"""On-the-fly WCS-WAVE click-to-spectrum extraction endpoint."""

from collections import OrderedDict
import json
import math
from pathlib import Path
import threading
from fastapi import APIRouter, Depends, Query

from app.config import Settings, get_settings
from app.core.errors import ExploreError
from app.data.cache import DiskCache
from app.models import SpectrumResult
from app.pipeline.session import find_session_dir
from app.science.spectrum import _subimage_bg_subtracted, extract_spectrum_at


router = APIRouter(prefix="/api/sessions", tags=["spectrum"])

_MAX_CACHED_SESSIONS = 3
_SUBIMAGE_CACHE: OrderedDict[tuple[str, int], list[dict]] = OrderedDict()
_SUBIMAGE_CACHE_LOCK = threading.Lock()


def _load_session_subimages(sdir: Path, settings: Settings, refs: list[dict]) -> list[dict]:
    """Decode and cache session subimages + WCS objects across clicks (bounded LRU)."""
    cache_key = (str(sdir.resolve()), len(refs))
    with _SUBIMAGE_CACHE_LOCK:
        cached = _SUBIMAGE_CACHE.get(cache_key)
        if cached is not None:
            _SUBIMAGE_CACHE.move_to_end(cache_key)
            return cached

    local_cache = DiskCache(sdir / "raw_subimages") if (sdir / "raw_subimages").exists() else None
    runtime_cache = DiskCache(settings.spx_cache_dir)
    subimages: list[dict] = []

    for ref in refs:
        sub = None
        if local_cache is not None:
            sub = local_cache.get_raw(
                ref["obs_id"], ref["detector"], ref["ra_deg"], ref["dec_deg"], ref["fov_deg"]
            )
        if sub is None:
            sub = runtime_cache.get_raw(
                ref["obs_id"], ref["detector"], ref["ra_deg"], ref["dec_deg"], ref["fov_deg"]
            )
        if sub is not None:
            # Precompute ZODI-subtracted Float32 array once for fast multi-click photometry
            _subimage_bg_subtracted(sub)
            subimages.append(sub)

    if subimages:
        with _SUBIMAGE_CACHE_LOCK:
            _SUBIMAGE_CACHE[cache_key] = subimages
            _SUBIMAGE_CACHE.move_to_end(cache_key)
            while len(_SUBIMAGE_CACHE) > _MAX_CACHED_SESSIONS:
                _SUBIMAGE_CACHE.popitem(last=False)

    return subimages


@router.get("/{session_id}/spectrum", response_model=SpectrumResult)
def get_spectrum(
    session_id: str,
    ra: float = Query(..., description="Clicked sky RA in decimal degrees"),
    dec: float = Query(..., ge=-90.0, le=90.0, description="Clicked sky Dec in decimal degrees"),
    settings: Settings = Depends(get_settings),
) -> SpectrumResult:
    """Extract live flux vs wavelength (um) across cached visits for clicked coordinates."""
    if not (math.isfinite(ra) and math.isfinite(dec)):
        raise ExploreError("BAD_COORDS", "Coordinates must be finite numbers.", 400)
    ra_norm = ra % 360.0

    sdir = find_session_dir(settings, session_id)

    # Return pre-baked spectrum instantaneously if within 2" of preset target center
    preset_spec_path = sdir / "spectrum.json"
    if preset_spec_path.exists():
        raw_spec = json.loads(preset_spec_path.read_text(encoding="utf-8"))
        d_ra = ((raw_spec["ra"] - ra_norm + 180.0) % 360.0 - 180.0) * math.cos(math.radians(dec))
        d_dec = raw_spec["dec"] - dec
        if math.hypot(d_ra, d_dec) * 3600.0 < 2.0:
            return SpectrumResult.model_validate(raw_spec)

    raw_refs_path = sdir / "raw_refs.json"
    if not raw_refs_path.exists():
        raise ExploreError("SPECTRUM_UNAVAILABLE", "Raw visit index missing for this session.", 404)

    refs = json.loads(raw_refs_path.read_text(encoding="utf-8"))
    subimages = _load_session_subimages(sdir, settings, refs)

    if not subimages:
        if preset_spec_path.exists():
            res = SpectrumResult.model_validate(json.loads(preset_spec_path.read_text(encoding="utf-8")))
            res.note = (res.note or "") + " Showing target center spectrum from preset bundle."
            return res
        raise ExploreError(
            "SPECTRUM_CACHE_EXPIRED",
            "Raw subimages expired from disposable cache; rerun Search to inspect arbitrary off-center pixels.",
            404,
        )

    return extract_spectrum_at(ra_norm, dec, subimages)
