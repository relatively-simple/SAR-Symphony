"""Automated tests for AI Story Director hotspot pattern detection on multi-sensor cubes."""

from pathlib import Path
import numpy as np
import pytest

from app.io.framepack import encode_framepack
from app.models import GridSpec, PatternCandidate, PatternReport, SessionManifest, TargetRef

try:
    from app.science.patterns import detect_patterns
except (ImportError, AttributeError):
    detect_patterns = None  # type: ignore


EARTH_PATTERN_KINDS = {"onset", "peak_impact", "blackout", "illusion"}


def _build_synthetic_earth_session(
    session_dir: Path,
    session_id: str = "test-session",
    with_blackout: bool = True,
    with_illusion: bool = True,
    with_surge: bool = True,
    coincident_coord: tuple[int, int] | None = None,
) -> SessionManifest:
    """Helper to generate a synthetic 12-frame multi-sensor SFP1 bundle for pattern testing."""
    frames_dir = session_dir / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)

    n_frames = 12
    npix = 64
    frame_ids = [f"f_{i:02d}" for i in range(n_frames)]

    # Base signals: calm baseline
    radar = np.full((n_frames, 1, npix, npix), -15.0, dtype=np.float32)
    rain = np.zeros((n_frames, 1, npix, npix), dtype=np.float32)
    wind = np.full((n_frames, 1, npix, npix), 3.0, dtype=np.float32)
    temp = np.full((n_frames, 1, npix, npix), 25.0, dtype=np.float32)
    optical = np.full((n_frames, 1, npix, npix), 0.75, dtype=np.float32)
    nightlights = np.full((n_frames, 1, npix, npix), 20.0, dtype=np.float32)
    flags = np.zeros((n_frames, npix, npix), dtype=np.uint16)

    cy, cx = coincident_coord if coincident_coord is not None else (None, None)

    # 1. Onset zone: Rain storm starts at (y=20, x=20) at frame 2
    if with_surge:
        y1, y2 = (cy - 2, cy + 3) if cy is not None else (18, 23)
        x1, x2 = (cx - 2, cx + 3) if cx is not None else (18, 23)
        rain[2:, 0, y1:y2, x1:x2] = 45.0

    # 2. Peak Impact zone: Flood inundation or fire front at (y=32, x=32) at frame 5
    if with_surge:
        # Radar drops drastically (specular water reflection)
        y1, y2 = (cy - 2, cy + 3) if cy is not None else (30, 35)
        x1, x2 = (cx - 2, cx + 3) if cx is not None else (30, 35)
        radar[4:8, 0, y1:y2, x1:x2] = -28.0

    # 3. Community Blackout: Nightlights drop from 20 -> 2 at (y=45, x=45) during peak
    if with_blackout:
        y1, y2 = (cy - 2, cy + 3) if cy is not None else (42, 48)
        x1, x2 = (cx - 2, cx + 3) if cx is not None else (42, 48)
        nightlights[4:8, 0, y1:y2, x1:x2] = 2.0  # 90% drop in radiance

    # 4. Radar Illusion: High wind over water causes high backscatter at (y=15, x=45)
    if with_illusion:
        y1, y2 = (cy - 2, cy + 3) if cy is not None else (13, 18)
        x1, x2 = (cx - 2, cx + 3) if cx is not None else (43, 48)
        wind[3:6, 0, y1:y2, x1:x2] = 14.0
        flags[3:6, y1:y2, x1:x2] = 0x0001  # Bit 1: Wind-Ripple Illusion

    # Derived products
    pass_coadds = radar.copy()
    diffs = radar - radar[0:1]
    rgb = np.zeros((n_frames, 3, npix, npix), dtype=np.float32)
    coldglow = temp.copy()

    products = {
        "radar": radar,
        "rain": rain,
        "wind": wind,
        "temp": temp,
        "optical": optical,
        "nightlights": nightlights,
        "pass_coadds": pass_coadds,
        "diffs": diffs,
        "rgb": rgb,
        "coldglow": coldglow,
    }

    for name, arr in products.items():
        blob = encode_framepack(frame_ids, arr, flags if name != "rgb" else None)
        (frames_dir / f"{name}.sfp").write_bytes(blob)

    manifest = SessionManifest(
        session_id=session_id,
        source="preset",
        target=TargetRef(ra=80.63, dec=7.29, name="Synthetic Event", slug=session_id),
        grid=GridSpec(ra0=80.63, dec0=7.29, fov_deg=0.5, npix=64),
        passes=[],
        products={},
        frames={},
        category="Flood",
        region_label="Synthetic Valley",
        created_utc="2026-11-15T00:00:00Z",
        pipeline_version="v2.0",
    )
    return manifest


# ==============================================================================
# Tier 1 & 3: Hotspot Candidate Detection
# ==============================================================================

def test_detect_patterns_identifies_earth_hotspots(tmp_path: Path) -> None:
    """Verify detect_patterns identifies Onset, Peak Impact, Blackout, and Illusion zones."""
    if detect_patterns is None:
        pytest.skip("app.science.patterns not yet implemented in M1")

    session_dir = tmp_path / "earth-session"
    manifest = _build_synthetic_earth_session(session_dir)

    report = detect_patterns(session_dir, manifest)

    assert isinstance(report, PatternReport)
    assert report.session_id == manifest.session_id
    assert report.n_patterns >= 1
    assert len(report.candidates) >= 1

    for cand in report.candidates:
        assert isinstance(cand, PatternCandidate)
        assert cand.id is not None
        assert cand.kind in EARTH_PATTERN_KINDS
        assert cand.confidence in {"High", "Medium"}
        assert cand.snr > 0.0
        assert 0.0 <= cand.fits_x < 64.0, f"fits_x {cand.fits_x} out of pixel bounds"
        assert 0.0 <= cand.fits_y < 64.0, f"fits_y {cand.fits_y} out of pixel bounds"
        assert len(cand.title) > 5
        assert len(cand.summary) > 10


def test_blackout_hotspot_detection(tmp_path: Path) -> None:
    """Verify that >50% nightlights loss triggers a Community Blackout candidate."""
    if detect_patterns is None:
        pytest.skip("app.science.patterns not yet implemented in M1")

    session_dir = tmp_path / "blackout-session"
    manifest = _build_synthetic_earth_session(session_dir, with_blackout=True, with_illusion=False, with_surge=False)

    report = detect_patterns(session_dir, manifest)

    blackout_cands = [c for c in report.candidates if c.kind == "blackout"]
    assert len(blackout_cands) >= 1, "Community Blackout candidate must be detected when nightlights drop >50%"
    bo = blackout_cands[0]
    assert bo.confidence == "High"
    assert "blackout" in bo.title.lower() or "power" in bo.title.lower() or "lights" in bo.title.lower()
    assert abs(bo.fits_x - 45.0) < 5.0
    assert abs(bo.fits_y - 45.0) < 5.0


def test_radar_illusion_hotspot_detection(tmp_path: Path) -> None:
    """Verify that Wind-Ripple or Sub-Zero flags trigger an AI-corrected Illusion hotspot."""
    if detect_patterns is None:
        pytest.skip("app.science.patterns not yet implemented in M1")

    session_dir = tmp_path / "illusion-session"
    manifest = _build_synthetic_earth_session(session_dir, with_blackout=False, with_illusion=True, with_surge=False)

    report = detect_patterns(session_dir, manifest)

    illusion_cands = [c for c in report.candidates if c.kind == "illusion"]
    assert len(illusion_cands) >= 1, "AI-corrected Radar Illusion hotspot must be detected when illusion flags are present"
    il = illusion_cands[0]
    assert abs(il.fits_x - 45.0) < 5.0
    assert abs(il.fits_y - 15.0) < 5.0


# ==============================================================================
# Tier 2: Boundary Value Analysis & Edge Cases
# ==============================================================================

def test_flat_cube_handles_gracefully(tmp_path: Path) -> None:
    """A uniform flat cube with zero variance must return an empty/graceful report without dividing by zero."""
    if detect_patterns is None:
        pytest.skip("app.science.patterns not yet implemented in M1")

    session_dir = tmp_path / "flat-session"
    manifest = _build_synthetic_earth_session(session_dir, with_blackout=False, with_illusion=False, with_surge=False)

    report = detect_patterns(session_dir, manifest)

    assert report is not None
    assert isinstance(report.candidates, list)
    assert len(report.candidates) == 0 or all(c.snr >= 0.0 for c in report.candidates)


def test_coincident_epicenter_hotspots_not_suppressed_by_cross_kind_dedup(tmp_path: Path) -> None:
    """Verify that Onset, Peak Impact, Blackout, and Illusion can all trigger at the same epicenter."""
    if detect_patterns is None:
        pytest.skip("app.science.patterns not yet implemented in M1")

    session_dir = tmp_path / "coincident-session"
    # All 4 phenomena co-located at (y=30, x=30)
    manifest = _build_synthetic_earth_session(
        session_dir,
        with_blackout=True,
        with_illusion=True,
        with_surge=True,
        coincident_coord=(30, 30),
    )

    report = detect_patterns(session_dir, manifest)
    kinds_found = {c.kind for c in report.candidates}
    assert kinds_found == {"onset", "peak_impact", "blackout", "illusion"}, (
        f"Expected all 4 candidate kinds at coincident epicenter, but got: {kinds_found}"
    )

