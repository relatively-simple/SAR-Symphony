"""API endpoint returning compiled SessionManifest JSON."""

from fastapi import APIRouter, Depends

from app.config import Settings, get_settings
from app.models import SessionManifest
from app.pipeline.session import load_manifest


router = APIRouter(prefix="/api/sessions", tags=["sessions"])


@router.get("/{session_id}", response_model=SessionManifest)
def get_session(session_id: str, settings: Settings = Depends(get_settings)) -> SessionManifest:
    """Return stored manifest for a preset or runtime session."""
    return load_manifest(settings, session_id)
