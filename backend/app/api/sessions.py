"""API endpoints returning compiled SessionManifest JSON and automated pattern reports."""

from collections import OrderedDict
import threading
from fastapi import APIRouter, Depends

from app.config import Settings, get_settings
from app.models import PatternReport, SessionManifest
from app.pipeline.session import find_session_dir, load_manifest
from app.science.patterns import detect_patterns


router = APIRouter(prefix="/api/sessions", tags=["sessions"])

_PATTERN_CACHE_MAX = 24
_PATTERN_CACHE: OrderedDict[tuple[str, str], PatternReport] = OrderedDict()
_PATTERN_CACHE_LOCK = threading.Lock()


@router.get("/{session_id}", response_model=SessionManifest)
def get_session(session_id: str, settings: Settings = Depends(get_settings)) -> SessionManifest:
    """Return stored manifest for a preset or runtime session."""
    return load_manifest(settings, session_id)


@router.get("/{session_id}/patterns", response_model=PatternReport)
def get_session_patterns(session_id: str, settings: Settings = Depends(get_settings)) -> PatternReport:
    """Compute (or return cached) automated spatial, variability, and cold-IR pattern detections."""
    sdir = find_session_dir(settings, session_id)
    key = (str(sdir.resolve()), session_id)
    with _PATTERN_CACHE_LOCK:
        cached = _PATTERN_CACHE.get(key)
        if cached is not None:
            _PATTERN_CACHE.move_to_end(key)
            return cached

    manifest = load_manifest(settings, session_id)
    report = detect_patterns(sdir, manifest)

    with _PATTERN_CACHE_LOCK:
        _PATTERN_CACHE[key] = report
        _PATTERN_CACHE.move_to_end(key)
        while len(_PATTERN_CACHE) > _PATTERN_CACHE_MAX:
            _PATTERN_CACHE.popitem(last=False)

    return report
