"""Pre-baked Earth event overlay loader."""

import json
from pathlib import Path

from app.models import OverlaySet


def load_preset_overlays(preset_root: Path, slug: str, mjd_ref: float | None = None) -> OverlaySet | None:
    """Load pre-baked Earth feature overlay metadata cleanly from preset cache."""
    p = preset_root / slug / "overlays.json"
    if not p.exists():
        return None
    data = json.loads(p.read_text(encoding="utf-8"))
    ov = OverlaySet.model_validate(data)
    if mjd_ref is not None:
        ov.mjd_ref = mjd_ref
    return ov
