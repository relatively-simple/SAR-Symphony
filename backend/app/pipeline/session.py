"""Session ID resolution, manifest persistence, and preset bundle loading."""

import hashlib
import json
import re
from pathlib import Path

from app.config import Settings
from app.core.errors import ExploreError
from app.models import CitationEntry, OverlaySet, SessionManifest


_SAFE_SESSION_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


DEFAULT_CITATIONS: list[CitationEntry] = [
    CitationEntry(
        label="SPHEREx DR1 Spectral Images",
        doi="10.26131/IRSA678",
        url="https://irsa.ipac.caltech.edu/data/SPHEREx/docs/overview_dr1.html",
        text=(
            "This publication makes use of data products from the Spectro-Photometer for the History of the Universe, "
            "Epoch of Reionization and Ices Explorer (SPHEREx), which is a joint project of the Jet Propulsion "
            "Laboratory and the California Institute of Technology, and is funded by the National Aeronautics and Space Administration."
        ),
    ),
    CitationEntry(
        label="SPHEREx QR3 Quick Release Images",
        doi="10.26131/IRSA662",
        url="https://irsa.ipac.caltech.edu/data/SPHEREx/docs/overview_qr.html",
        text="Uniformly processed Quick Release 3 spectral images combined with DR1 via NASA/IPAC IRSA SIAv2.",
    ),
    CitationEntry(
        label="Gaia DR3 & AllWISE / CDS Aladin Lite",
        url="https://irsa.ipac.caltech.edu/Missions/gaia.html",
        text="Cross-mission astrometric & infrared overlays powered by ESA/IRSA Gaia DR3, NASA AllWISE, and CDS Aladin Lite v3.",
    ),
]


def make_session_id(ra_deg: float, dec_deg: float, fov_deg: float, collections: list[str], pipeline_version: str) -> str:
    """Create deterministic compact session ID from query parameters."""
    raw = f"{ra_deg:.4f}|{dec_deg:.4f}|{fov_deg:.3f}|{','.join(collections)}|{pipeline_version}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]


def find_session_dir(settings: Settings, session_id: str) -> Path:
    """Resolve existing preset or runtime session directory, raising ExploreError on invalid/missing ID."""
    if not _SAFE_SESSION_ID_RE.match(session_id):
        raise ExploreError("INVALID_SESSION_ID", f"Invalid session identifier '{session_id}'.", 400)
    preset_root = settings.spx_preset_dir.resolve()
    preset_dir = (preset_root / session_id).resolve()
    if preset_dir.is_relative_to(preset_root) and (preset_dir / "manifest.json").exists():
        return preset_dir
    live_root = (settings.spx_cache_dir / "sessions").resolve()
    live_dir = (live_root / session_id).resolve()
    if live_dir.is_relative_to(live_root) and (live_dir / "manifest.json").exists():
        return live_dir
    raise ExploreError("SESSION_NOT_FOUND", f"Session '{session_id}' not found or expired.", 404)


def load_manifest(settings: Settings, session_id: str) -> SessionManifest:
    """Load SessionManifest JSON from preset directory or runtime cache."""
    sdir = find_session_dir(settings, session_id)
    raw = json.loads((sdir / "manifest.json").read_text(encoding="utf-8"))
    return SessionManifest.model_validate(raw)


def save_manifest(session_dir: Path, manifest: SessionManifest) -> Path:
    """Persist SessionManifest JSON atomically."""
    session_dir.mkdir(parents=True, exist_ok=True)
    p = session_dir / "manifest.json"
    p.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
    return p


def load_preset_spectrum(preset_dir: Path, slug: str) -> dict | None:
    p = preset_dir / slug / "spectrum.json"
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return None


def list_ready_presets(preset_dir: Path) -> list[str]:
    if not preset_dir.exists():
        return []
    return sorted(
        d.name for d in preset_dir.iterdir()
        if d.is_dir() and (d / "manifest.json").exists()
    )
