"""Session ID resolution, manifest persistence, and preset bundle loading for Dancing with the SARs."""

import hashlib
import json
from pathlib import Path
import re

from app.config import Settings
from app.core.errors import ExploreError
from app.models import CitationEntry, OverlaySet, SessionManifest


_SAFE_SESSION_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


DEFAULT_CITATIONS: list[CitationEntry] = [
    CitationEntry(
        label="NASA-ISRO SAR (NISAR) & Copernicus Sentinel-1",
        doi="10.5067/SENTINEL-1/SAR_GRD",
        url="https://nisar.jpl.nasa.gov/",
        text="L-band & C-band Synthetic Aperture Radar (SAR) backscatter observations provided via NASA ASF DAAC and ESA Copernicus.",
    ),
    CitationEntry(
        label="NASA Global Precipitation Measurement (GPM IMERG)",
        doi="10.5067/GPM/IMERG/3B-HH/07",
        url="https://gpm.nasa.gov/data/imerg",
        text="Half-hourly multi-satellite precipitation estimates from the NASA GPM Integrated Multi-satellitE Retrievals for GPM (IMERG).",
    ),
    CitationEntry(
        label="NASA MERRA-2 Atmospheric Reanalysis",
        doi="10.5067/A7S6XP56VZWS",
        url="https://gmao.gsfc.nasa.gov/reanalysis/MERRA-2/",
        text="Surface wind speed and vector fields from the Modern-Era Retrospective analysis for Research and Applications, Version 2.",
    ),
    CitationEntry(
        label="NASA Black Marble Nighttime Lights (VNP46A2)",
        doi="10.5067/VIIRS/VNP46A2.001",
        url="https://blackmarble.gsfc.nasa.gov/",
        text="Daily moonlight- and atmosphere-corrected Day/Night Band nocturnal radiance product from Suomi-NPP VIIRS.",
    ),
    CitationEntry(
        label="Copernicus Sentinel-2 & NASA VIIRS NDVI",
        url="https://www.copernicus.eu/en/access-data",
        text="Multi-spectral high-resolution optical surface reflectance and Normalized Difference Vegetation Index (NDVI).",
    ),
    CitationEntry(
        label="NASA Earth Observatory Natural Event Tracker (EONET v3)",
        url="https://eonet.gsfc.nasa.gov/api/v3/events",
        text="Real-time global natural hazards and disaster curation provided by NASA Goddard Space Flight Center.",
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
