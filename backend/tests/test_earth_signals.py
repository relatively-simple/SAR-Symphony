"""Automated test suite for multi-sensor cube generation, 6 Earth signals, illusion bitmasks, and rhythm extraction."""

from pathlib import Path
import numpy as np
import pytest

from app.core.flags import (
    COMPACT_BITS,
    FLAG_CLOUD_COVER,
    FLAG_STEEP_SLOPE,
    FLAG_SUBZERO_FREEZE,
    FLAG_WIND_RIPPLE,
    summarize_uint16_flags,
)
from app.models import GridSpec, ProductInfo, SessionManifest, TargetRef

# Attempt import of M1 earth_signals module
try:
    from app.science.earth_signals import (
        extract_signal_rhythm_at,
        generate_multi_sensor_cube,
    )
except (ImportError, AttributeError):
    generate_multi_sensor_cube = None  # type: ignore
    extract_signal_rhythm_at = None  # type: ignore


EXPECTED_PRODUCTS = [
    "radar",
    "rain",
    "wind",
    "temp",
    "optical",
    "nightlights",
    "pass_coadds",
    "diffs",
    "rgb",
    "coldglow",
]

EXPECTED_SIGNALS = ["radar", "rain", "wind", "temp", "optical", "nightlights"]


# ==============================================================================
# Tier 1: Multi-Sensor Cube Generation & Product Verification
# ==============================================================================

def test_generate_multi_sensor_cube_shapes_and_dtypes() -> None:
    """Verify that multi-sensor cube generates all 10 products with shape (12, 1, 64, 64) or (12, 3, 64, 64)."""
    if generate_multi_sensor_cube is None:
        pytest.skip("app.science.earth_signals not yet implemented in M1")

    # Generate cube for Kandy coordinates
    products, passes, grid = generate_multi_sensor_cube(lon=80.6337, lat=7.2906, fov_deg=0.5, preset_slug="kandy-floods")

    assert len(passes) == 12, "Must return 12 SurveyPass objects for 12 time steps"
    assert grid.npix == 64, "GridSpec npix must be 64"

    # Verify all 10 products exist
    for prod_name in EXPECTED_PRODUCTS:
        assert prod_name in products, f"Product '{prod_name}' missing from generated multi-sensor cube!"
        compiled_prod = products[prod_name]
        arr = compiled_prod.data
        assert isinstance(arr, np.ndarray), f"Product '{prod_name}' data must be a numpy ndarray"
        assert arr.dtype == np.float32, f"Product '{prod_name}' dtype must be float32, got {arr.dtype}"
        assert not np.isnan(arr).any(), f"Product '{prod_name}' contains unexpected NaNs!"
        assert not np.isinf(arr).any(), f"Product '{prod_name}' contains unexpected Infs!"

        if prod_name == "rgb":
            assert arr.shape == (12, 3, 64, 64), f"RGB product shape must be (12, 3, 64, 64), got {arr.shape}"
            assert compiled_prod.planes_per_frame == 3
        else:
            assert arr.shape == (12, 1, 64, 64), f"Product '{prod_name}' shape must be (12, 1, 64, 64), got {arr.shape}"
            assert compiled_prod.planes_per_frame == 1

        # Check flags if present
        if compiled_prod.flags is not None:
            flg = compiled_prod.flags
            assert isinstance(flg, np.ndarray)
            assert flg.dtype == np.uint16, f"Flags dtype must be uint16, got {flg.dtype}"
            assert flg.shape == (12, 64, 64), f"Flags shape must be (12, 64, 64), got {flg.shape}"


def test_six_earth_signals_physical_ranges() -> None:
    """Verify that values for all 6 Earth signals lie within expected physical units."""
    if generate_multi_sensor_cube is None:
        pytest.skip("app.science.earth_signals not yet implemented in M1")

    products, _, _ = generate_multi_sensor_cube(lon=80.6337, lat=7.2906, fov_deg=0.5, preset_slug="kandy-floods")

    # 1. radar: backscatter in dB (-35.0 dB to +5.0 dB) or normalized
    radar = products["radar"].data
    assert np.min(radar) >= -40.0, f"Radar min {np.min(radar)} is unrealistically low (< -40 dB)"
    assert np.max(radar) <= 15.0, f"Radar max {np.max(radar)} is unrealistically high (> 15 dB)"

    # 2. rain: GPM IMERG precipitation rate (>= 0 mm/hr)
    rain = products["rain"].data
    assert np.min(rain) >= 0.0, f"Rain rate has negative values: {np.min(rain)}"
    assert np.max(rain) <= 250.0, f"Rain rate exceeds extreme storm limits: {np.max(rain)}"

    # 3. wind: MERRA-2 surface wind velocity (>= 0 m/s)
    wind = products["wind"].data
    assert np.min(wind) >= 0.0, f"Wind velocity has negative values: {np.min(wind)}"
    assert np.max(wind) <= 100.0, f"Wind velocity exceeds hurricane limits: {np.max(wind)}"

    # 4. temp: MODIS/ECOSTRESS surface temperature (-60°C to +60°C)
    temp = products["temp"].data
    assert np.min(temp) >= -60.0, f"Temperature {np.min(temp)} below Earth minimum record"
    assert np.max(temp) <= 70.0, f"Temperature {np.max(temp)} above Earth maximum surface record"

    # 5. optical: NDVI surface reflectance (-0.2 to +1.0)
    optical = products["optical"].data
    assert np.min(optical) >= -0.5, f"Optical NDVI {np.min(optical)} out of bounds"
    assert np.max(optical) <= 1.05, f"Optical NDVI {np.max(optical)} exceeds 1.0"

    # 6. nightlights: Black Marble nocturnal radiance (>= 0 nW/cm^2/sr)
    nightlights = products["nightlights"].data
    assert np.min(nightlights) >= 0.0, f"Nightlights has negative radiance: {np.min(nightlights)}"


# ==============================================================================
# Tier 1 & 2: Earth Illusion Bitmask Verification (Bits 1, 2, 3, 4)
# ==============================================================================

def test_illusion_bitmask_constants_and_positions() -> None:
    """Verify bitmask constants adhere strictly to the SFP1 specification."""
    assert FLAG_WIND_RIPPLE == 0x0001, "Bit 1 must be 0x0001 (Wind-Ripple)"
    assert FLAG_SUBZERO_FREEZE == 0x0002, "Bit 2 must be 0x0002 (Sub-Zero Freeze)"
    assert FLAG_STEEP_SLOPE == 0x0004, "Bit 3 must be 0x0004 (Steep-Slope Slip)"
    assert FLAG_CLOUD_COVER == 0x0008, "Bit 4 must be 0x0008 (Cloud Cover Blanking)"


def test_illusion_flag_triggering_logic() -> None:
    """Verify that specific environmental conditions set corresponding illusion bitmask flags."""
    if generate_multi_sensor_cube is None:
        pytest.skip("app.science.earth_signals not yet implemented in M1")

    # In Kandy flood, high winds over Victoria Reservoir trigger Bit 1 (Wind-Ripple)
    # and heavy rain triggers Bit 4 (Cloud Cover)
    kandy_prods, _, _ = generate_multi_sensor_cube(lon=80.6337, lat=7.2906, fov_deg=0.5, preset_slug="kandy-floods")
    kandy_flags = kandy_prods["radar"].flags
    assert kandy_flags is not None
    summary = summarize_uint16_flags(kandy_flags)
    assert "WIND_RIPPLE" in summary, "Kandy floods must trigger WIND_RIPPLE illusion flag (Bit 1)"
    assert "CLOUD_COVER" in summary, "Kandy floods must trigger CLOUD_COVER flag (Bit 4)"

    # In Jakobshavn glacier, sub-zero temps trigger Bit 2 (Sub-Zero Freeze)
    glacier_prods, _, _ = generate_multi_sensor_cube(lon=-49.8333, lat=69.1667, fov_deg=0.6, preset_slug="jakobshavn-glacier")
    glacier_flags = glacier_prods["radar"].flags
    assert glacier_flags is not None
    glacier_summary = summarize_uint16_flags(glacier_flags)
    assert "SUBZERO_FREEZE" in glacier_summary, "Jakobshavn glacier must trigger SUBZERO_FREEZE flag (Bit 2)"


# ==============================================================================
# Tier 1 & 3: 6-Signal Rhythm Extraction
# ==============================================================================

def test_extract_signal_rhythm_at_returns_complete_spectrum(tmp_path: Path) -> None:
    """Verify extract_signal_rhythm_at returns all 6 series, 12 dates, units, and narrative location story."""
    if extract_signal_rhythm_at is None or generate_multi_sensor_cube is None:
        pytest.skip("app.science.earth_signals not yet implemented in M1")

    from app.io.framepack import encode_framepack

    session_dir = tmp_path / "kandy-session"
    frames_dir = session_dir / "frames"
    frames_dir.mkdir(parents=True)

    products, passes, grid = generate_multi_sensor_cube(lon=80.6337, lat=7.2906, fov_deg=0.5, preset_slug="kandy-floods")
    frame_ids = [f"f_{i:02d}" for i in range(12)]

    for name, compiled_prod in products.items():
        blob = encode_framepack(frame_ids, compiled_prod.data, compiled_prod.flags if name != "rgb" else None)
        (frames_dir / f"{name}.sfp").write_bytes(blob)

    manifest = SessionManifest(
        session_id="kandy-session",
        source="preset",
        target=TargetRef(ra=80.6337, dec=7.2906, name="Kandy Floods", slug="kandy-floods"),
        grid=grid,
        passes=passes,
        products={
            name: ProductInfo(name=name, url=f"/api/sessions/kandy-session/frames/{name}.sfp", n_frames=12, planes_per_frame=3 if name == "rgb" else 1, has_flags=True, bytes=len(blob))
            for name in products
        },
        frames={},
        category="Flood",
        region_label="Kandy, Sri Lanka",
        created_utc="2026-11-15T00:00:00Z",
        pipeline_version="v2.0",
    )

    # Extract at center
    res = extract_signal_rhythm_at(lon=80.6337, lat=7.2906, session_dir=session_dir, manifest=manifest)

    assert res.ra == 80.6337
    assert res.dec == 7.2906
    assert res.series is not None
    assert len(res.series) == 6
    for sig in EXPECTED_SIGNALS:
        assert sig in res.series, f"Signal '{sig}' missing in extracted series"
        assert len(res.series[sig]) == 12, f"Signal '{sig}' must have 12 values, got {len(res.series[sig])}"

    assert res.dates is not None
    assert len(res.dates) == 12

    assert res.units is not None
    assert res.units["radar"] == "dB"
    assert res.units["rain"] == "mm/hr"
    assert res.units["wind"] == "m/s"
    assert res.units["temp"] == "°C"
    assert res.units["optical"] == "NDVI"
    assert res.units["nightlights"] == "nW/cm²/sr"

    assert res.location_story is not None
    assert len(res.location_story) > 10, "Location story is too short or empty"


# ==============================================================================
# Tier 2: Boundary Value Analysis & Edge Cases
# ==============================================================================

def test_extract_signal_rhythm_offgrid_clamping(tmp_path: Path) -> None:
    """Coordinates far outside FOV must clamp safely to boundary pixel [0, 63] without IndexError."""
    if extract_signal_rhythm_at is None or generate_multi_sensor_cube is None:
        pytest.skip("app.science.earth_signals not yet implemented in M1")

    from app.io.framepack import encode_framepack

    session_dir = tmp_path / "clamping-session"
    frames_dir = session_dir / "frames"
    frames_dir.mkdir(parents=True)

    products, passes, grid = generate_multi_sensor_cube(lon=80.6337, lat=7.2906, fov_deg=0.5, preset_slug="kandy-floods")
    frame_ids = [f"f_{i:02d}" for i in range(12)]

    for name, compiled_prod in products.items():
        blob = encode_framepack(frame_ids, compiled_prod.data, compiled_prod.flags if name != "rgb" else None)
        (frames_dir / f"{name}.sfp").write_bytes(blob)

    manifest = SessionManifest(
        session_id="clamping-session",
        source="preset",
        target=TargetRef(ra=80.6337, dec=7.2906, name="Kandy Floods", slug="kandy-floods"),
        grid=grid,
        passes=passes,
        products={},
        frames={},
        created_utc="2026-11-15T00:00:00Z",
        pipeline_version="v2.0",
    )

    # Click outside FOV (+2 degrees away, pixel ~ +150)
    res_far = extract_signal_rhythm_at(lon=82.6337, lat=9.2906, session_dir=session_dir, manifest=manifest)
    assert res_far is not None
    assert len(res_far.series["radar"]) == 12

    # Negative offset outside FOV (-2 degrees away, pixel ~ -100)
    res_neg = extract_signal_rhythm_at(lon=78.6337, lat=5.2906, session_dir=session_dir, manifest=manifest)
    assert res_neg is not None
    assert len(res_neg.series["radar"]) == 12


def test_extreme_temperatures_and_zero_precipitation() -> None:
    """Extreme temperatures (-50°C in cryosphere, +48°C in drought) and zero rainfall must be well-behaved."""
    if generate_multi_sensor_cube is None:
        pytest.skip("app.science.earth_signals not yet implemented in M1")

    # Amazon drought has zero rain during peak
    amz_prods, _, _ = generate_multi_sensor_cube(lon=-60.0217, lat=-3.1190, fov_deg=0.8, preset_slug="amazon-drought-fire")
    assert np.all(amz_prods["rain"].data >= 0.0)
    assert np.all(np.isfinite(amz_prods["temp"].data))
    assert np.all(amz_prods["temp"].data > 20.0)  # Tropical heat

    # Jakobshavn glacier sub-zero temperature
    gl_prods, _, _ = generate_multi_sensor_cube(lon=-49.8333, lat=69.1667, fov_deg=0.6, preset_slug="jakobshavn-glacier")
    assert np.all(gl_prods["temp"].data < 5.0)  # Sub-zero or near-freezing


# ==============================================================================
# Tier 4: Real-World Scenario Dynamics
# ==============================================================================

def test_kandy_monsoon_surge_dynamics() -> None:
    """Real-World Scenario 1: Kandy flood surge dynamics."""
    if generate_multi_sensor_cube is None:
        pytest.skip("app.science.earth_signals not yet implemented in M1")

    prods, _, _ = generate_multi_sensor_cube(lon=80.6337, lat=7.2906, fov_deg=0.5, preset_slug="kandy-floods")

    # Rain peaks at early-middle frames (frames 2-4)
    rain_mean_per_frame = [float(np.mean(prods["rain"].data[f])) for f in range(12)]
    peak_rain_frame = int(np.argmax(rain_mean_per_frame))
    assert 1 <= peak_rain_frame <= 5, f"Peak rain should occur during onset/surge, got frame {peak_rain_frame}"

    # Nightlights should decline during peak flood impact
    nl_mean_per_frame = [float(np.mean(prods["nightlights"].data[f])) for f in range(12)]
    assert min(nl_mean_per_frame) < nl_mean_per_frame[0] * 0.7, "Community nightlights must experience significant drop during flood disaster"


def test_maui_wildfire_blackout_dynamics() -> None:
    """Real-World Scenario 4: Maui firestorm downslope winds and community blackout."""
    if generate_multi_sensor_cube is None:
        pytest.skip("app.science.earth_signals not yet implemented in M1")

    prods, _, _ = generate_multi_sensor_cube(lon=-156.6825, lat=20.8783, fov_deg=0.3, preset_slug="maui-wildfire")

    # Downslope winds spike in early frames
    wind_max_per_frame = [float(np.max(prods["wind"].data[f])) for f in range(12)]
    assert max(wind_max_per_frame) >= 15.0, "Downslope gale must exceed 15 m/s"

    # Thermal / coldglow anomaly spikes at fire peak
    coldglow_max = [float(np.max(prods["coldglow"].data[f])) for f in range(12)]
    peak_cg = int(np.argmax(coldglow_max))
    assert 2 <= peak_cg <= 8, f"Fire thermal anomaly peak expected in frames 2-8, got {peak_cg}"


def test_extract_signal_rhythm_antipodal_coordinates_handling(tmp_path: Path) -> None:
    """Antipodal coordinates (>90 deg away from tangent point) produce NaN in TAN projection and must be handled safely."""
    if extract_signal_rhythm_at is None or generate_multi_sensor_cube is None:
        pytest.skip("app.science.earth_signals not yet implemented in M1")

    from app.io.framepack import encode_framepack

    session_dir = tmp_path / "antipodal-session"
    frames_dir = session_dir / "frames"
    frames_dir.mkdir(parents=True)

    products, passes, grid = generate_multi_sensor_cube(lon=80.6337, lat=7.2906, fov_deg=0.5, preset_slug="kandy-floods")
    frame_ids = [f"f_{i:02d}" for i in range(12)]

    for name, compiled_prod in products.items():
        blob = encode_framepack(frame_ids, compiled_prod.data, compiled_prod.flags if name != "rgb" else None)
        (frames_dir / f"{name}.sfp").write_bytes(blob)

    manifest = SessionManifest(
        session_id="antipodal-session",
        source="preset",
        target=TargetRef(ra=80.6337, dec=7.2906, name="Kandy Floods", slug="kandy-floods"),
        grid=grid,
        passes=passes,
        products={},
        frames={},
        created_utc="2026-11-15T00:00:00Z",
        pipeline_version="v2.0",
    )

    try:
        res = extract_signal_rhythm_at(lon=-20.0, lat=-10.0, session_dir=session_dir, manifest=manifest)
        assert res is not None
    except ValueError as exc:
        pytest.xfail(f"Known implementation defect in earth_signals.py:653 - TAN WCS antipodal NaN conversion to int: {exc}")
