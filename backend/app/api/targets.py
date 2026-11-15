"""API endpoints for NASA Challenge 12 benchmark presets."""

from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse

from app.config import Settings, get_settings
from app.core.errors import ExploreError
from app.core.presets import PRESETS, list_presets
from app.models import SessionManifest, TargetPreset
from app.pipeline.session import list_ready_presets, load_manifest


router = APIRouter(prefix="/api/targets", tags=["targets"])


@router.get("", response_model=list[TargetPreset])
def get_targets(
    q: str | None = Query(None, description="Search query filtering by title, slug, or category"),
    settings: Settings = Depends(get_settings),
) -> list[TargetPreset]:
    """Return official NASA benchmark targets with pre-baked cache status and optional search filtering."""
    ready = set(list_ready_presets(settings.spx_preset_dir))
    items = []
    for preset in list_presets():
        copy = preset.model_copy(update={"has_preset_bundle": preset.slug in ready})
        items.append(copy)
    if q:
        needle = q.strip().lower()
        items = [
            p
            for p in items
            if needle in p.slug.lower()
            or needle in (p.title or "").lower()
            or needle in (p.name or "").lower()
            or needle in (p.category or "").lower()
            or needle in (p.region_label or "").lower()
        ]
    return items


@router.get("/{slug}", response_model=SessionManifest)
def get_target_session(slug: str, settings: Settings = Depends(get_settings)) -> SessionManifest:
    """Return compiled SessionManifest directly from cache/presets/<slug>."""
    if slug not in PRESETS:
        raise ExploreError("TARGET_NOT_FOUND", f"Unknown target slug '{slug}'.", 404)
    return load_manifest(settings, slug)


@router.get("/{slug}/thumb.webp")
def get_target_thumb(slug: str, settings: Settings = Depends(get_settings)) -> FileResponse:
    """Serve pre-rendered WebP mission card preview thumbnail."""
    if slug not in PRESETS:
        raise ExploreError("TARGET_NOT_FOUND", f"Unknown target slug '{slug}'.", 404)
    tpath = settings.spx_preset_dir / slug / "thumb.webp"
    if not tpath.exists():
        raise ExploreError("THUMB_MISSING", f"Thumbnail missing for '{slug}'.", 404)
    return FileResponse(tpath, media_type="image/webp", headers={"Cache-Control": "public, max-age=86400"})
