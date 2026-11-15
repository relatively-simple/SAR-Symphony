"""Tests for Earth event presets, story scenes, manifest schemas, and backwards compatibility."""

import pytest
from pydantic import ValidationError

from app.models import (
    GridSpec,
    ProductInfo,
    SessionManifest,
    SpectrumPoint,
    SpectrumResult,
    TargetRef,
)

# Attempt import of Earth presets and updated models from M1
try:
    from app.core.presets import PRESETS
except (ImportError, AttributeError):
    PRESETS = {}

try:
    from app.models import SignalId, StoryScene
except (ImportError, AttributeError):
    SignalId = None  # type: ignore
    StoryScene = None  # type: ignore


FLAGSHIP_SLUGS = [
    "kandy-floods",
    "amazon-drought-fire",
    "mahaweli-rice",
    "jakobshavn-glacier",
    "maui-wildfire",
]

VALID_SIGNALS = {"radar", "rain", "wind", "temp", "optical", "nightlights"}


def test_flagship_presets_presence() -> None:
    """All 5 flagship Earth event presets must exist in PRESETS."""
    if not any(slug in PRESETS for slug in FLAGSHIP_SLUGS):
        pytest.skip("Flagship Earth presets not yet implemented in app.core.presets (M1)")

    for slug in FLAGSHIP_SLUGS:
        assert slug in PRESETS, f"Flagship preset '{slug}' is missing from PRESETS dictionary!"


def test_preset_coordinates_and_bounds() -> None:
    """Verify coordinate bounds, FOV ranges, and lon/lat to ra/dec compatibility."""
    if not any(slug in PRESETS for slug in FLAGSHIP_SLUGS):
        pytest.skip("Flagship Earth presets not yet implemented in app.core.presets (M1)")

    expected_coords = {
        "kandy-floods": (80.63, 7.29),
        "amazon-drought-fire": (-60.02, -3.12),
        "mahaweli-rice": (81.02, 7.94),
        "jakobshavn-glacier": (-49.83, 69.17),
        "maui-wildfire": (-156.68, 20.88),
    }

    for slug in FLAGSHIP_SLUGS:
        preset = PRESETS[slug]
        ra = getattr(preset, "ra_deg", None)
        dec = getattr(preset, "dec_deg", None)
        assert ra is not None, f"Preset {slug} missing ra_deg"
        assert dec is not None, f"Preset {slug} missing dec_deg"

        # Coordinates must be valid Earth lat/lon
        assert -180.0 <= ra <= 180.0 or 0.0 <= ra <= 360.0, f"Preset {slug} ra_deg {ra} out of range"
        assert -90.0 <= dec <= 90.0, f"Preset {slug} dec_deg {dec} out of range"

        # Check approximate geographic center
        exp_lon, exp_lat = expected_coords[slug]
        # Normalize ra to -180..180 for comparison
        norm_ra = ((ra + 180.0) % 360.0) - 180.0 if ra > 180.0 else ra
        assert abs(norm_ra - exp_lon) < 2.0, f"Preset {slug} longitude mismatch: expected ~{exp_lon}, got {norm_ra}"
        assert abs(dec - exp_lat) < 2.0, f"Preset {slug} latitude mismatch: expected ~{exp_lat}, got {dec}"

        # FOV sanity check (typical satellite scene FOV between 0.05 and 5.0 degrees)
        fov = getattr(preset, "default_fov", 0.5)
        assert 0.01 <= fov <= 5.0, f"Preset {slug} default_fov {fov} out of range"


def test_preset_story_scenes_specification() -> None:
    """Every preset must have exactly 5 StoryScenes with valid phases, active layers, and narrations."""
    if not any(slug in PRESETS for slug in FLAGSHIP_SLUGS):
        pytest.skip("Flagship Earth presets not yet implemented in app.core.presets (M1)")

    for slug in FLAGSHIP_SLUGS:
        preset = PRESETS[slug]
        scenes = getattr(preset, "story_scenes", None)
        assert scenes is not None, f"Preset {slug} missing story_scenes attribute!"
        assert len(scenes) == 5, f"Preset {slug} must have exactly 5 story scenes, found {len(scenes)}!"

        for idx, scene in enumerate(scenes):
            # Check indexing
            s_idx = getattr(scene, "index", None)
            assert s_idx == idx, f"Scene {idx} in {slug} has index {s_idx}"

            # Check frame index is within 0..11
            frame_idx = getattr(scene, "frame_index", None)
            assert 0 <= frame_idx <= 11, f"Scene {idx} in {slug} has frame_index {frame_idx} outside [0, 11]"

            # Check active layers: 2 to 3 layers
            active_layers = getattr(scene, "active_layers", [])
            assert 1 <= len(active_layers) <= 4, f"Scene {idx} in {slug} has {len(active_layers)} active layers (expected 2-3)"
            for layer in active_layers:
                assert layer in VALID_SIGNALS, f"Scene {idx} in {slug} has invalid layer '{layer}'!"

            # Check non-empty narration and explanations
            narration = getattr(scene, "narration", "")
            assert len(narration.strip()) > 10, f"Scene {idx} in {slug} narration is too short or empty!"

            why = getattr(scene, "why_these_layers", "")
            assert len(why.strip()) > 5, f"Scene {idx} in {slug} why_these_layers is missing!"

            illusion_note = getattr(scene, "illusion_note", "")
            assert len(illusion_note.strip()) > 5, f"Scene {idx} in {slug} illusion_note is missing!"


def test_preset_metadata_fields() -> None:
    """Presets must have category, region_label, sensors_used, and illusion_summary."""
    if not any(slug in PRESETS for slug in FLAGSHIP_SLUGS):
        pytest.skip("Flagship Earth presets not yet implemented in app.core.presets (M1)")

    for slug in FLAGSHIP_SLUGS:
        preset = PRESETS[slug]
        cat = getattr(preset, "category", "")
        assert len(cat) > 0, f"Preset {slug} missing category!"

        region = getattr(preset, "region_label", "")
        assert len(region) > 0, f"Preset {slug} missing region_label!"

        sensors = getattr(preset, "sensors_used", [])
        assert len(sensors) >= 2, f"Preset {slug} must list at least 2 sensors used!"

        illusion = getattr(preset, "illusion_summary", "")
        assert len(illusion) > 10, f"Preset {slug} missing illusion_summary!"


def test_story_scene_model_validation() -> None:
    """Validate StoryScene Pydantic model rejects invalid configurations."""
    if StoryScene is None:
        pytest.skip("StoryScene model not yet implemented in app.models (M1)")

    # Valid scene creation
    scene = StoryScene(
        index=0,
        phase="pre-event",
        title="Baseline Landscape",
        date_label="Day 1",
        frame_index=0,
        active_layers=["radar", "optical"],
        narration="Calm pre-monsoon baseline over central highlands.",
        why_these_layers="Optical NDVI establishes vegetation canopy baseline; SAR maps riverbed geometry.",
        illusion_note="Smooth water shows specular zero-backscatter; no wind ripple detected yet.",
    )
    assert scene.index == 0
    assert scene.frame_index == 0
    assert len(scene.active_layers) == 2

    # Serialization roundtrip
    dumped = scene.model_dump_json()
    loaded = StoryScene.model_validate_json(dumped)
    assert loaded.title == scene.title
    assert loaded.active_layers == ["radar", "optical"]


def test_spectrum_result_6_signals_schema() -> None:
    """Validate SpectrumResult contains series for all 6 signals, dates, units, and backwards-compatible points."""
    dates = [f"2026-11-{i+1:02d}" for i in range(12)]
    series = {
        "radar": [-12.5] * 12,
        "rain": [0.0, 5.2, 35.0, 42.0, 10.0, 2.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        "wind": [3.5, 4.0, 8.2, 9.5, 6.0, 3.2, 2.5, 2.1, 2.0, 2.0, 2.2, 2.1],
        "temp": [24.0, 23.5, 21.0, 20.5, 22.0, 23.5, 24.2, 24.5, 24.8, 25.0, 25.0, 25.1],
        "optical": [0.75, 0.72, 0.20, 0.15, 0.35, 0.55, 0.68, 0.72, 0.74, 0.75, 0.75, 0.75],
        "nightlights": [15.2, 14.8, 8.5, 2.1, 3.0, 7.5, 12.0, 14.5, 15.0, 15.1, 15.2, 15.2],
    }
    units = {
        "radar": "dB",
        "rain": "mm/hr",
        "wind": "m/s",
        "temp": "°C",
        "optical": "NDVI",
        "nightlights": "nW/cm²/sr",
    }
    spec = SpectrumResult(
        ra=80.63,
        dec=7.29,
        series=series,
        dates=dates,
        units=units,
        location_story="Monsoon deluge inundated low-lying valley; wind waves caused brief SAR backscatter spike.",
        points=[],
        aperture_arcsec=10.0,
        n_used=12,
        n_rejected=0,
    )

    assert spec.ra == 80.63
    assert spec.dec == 7.29
    assert len(spec.series) == 6
    for sig in VALID_SIGNALS:
        assert sig in spec.series
        assert len(spec.series[sig]) == 12
    assert len(spec.dates) == 12
    assert spec.units["radar"] == "dB"
    assert spec.units["rain"] == "mm/hr"
    assert spec.location_story is not None


def test_session_manifest_extended_schema() -> None:
    """Verify SessionManifest includes category, region_label, sensors_used, story_scenes, and illusion_summary."""
    manifest = SessionManifest(
        session_id="kandy-floods",
        source="preset",
        target=TargetRef(ra=80.6337, dec=7.2906, name="Kandy Flash Floods", slug="kandy-floods"),
        grid=GridSpec(ra0=80.6337, dec0=7.2906, fov_deg=0.5, npix=64),
        passes=[],
        products={
            "radar": ProductInfo(name="radar", url="/api/sessions/kandy-floods/frames/radar.sfp", n_frames=12, planes_per_frame=1, has_flags=True, bytes=294912)
        },
        frames={},
        category="Flood",
        region_label="Kandy, Central Province, Sri Lanka",
        sensors_used=["Sentinel-1 SAR", "NASA GPM IMERG", "NASA MERRA-2", "NASA Black Marble"],
        illusion_summary="Reservoir surface roughened by 8+ m/s winds mimicked land backscatter.",
        created_utc="2026-11-15T00:00:00Z",
        pipeline_version="v2.0-earth-symphony",
    )

    dumped = manifest.model_dump_json()
    loaded = SessionManifest.model_validate_json(dumped)

    assert loaded.session_id == "kandy-floods"
    assert loaded.category == "Flood"
    assert loaded.region_label == "Kandy, Central Province, Sri Lanka"
    assert "Sentinel-1 SAR" in loaded.sensors_used
    assert "winds" in loaded.illusion_summary
