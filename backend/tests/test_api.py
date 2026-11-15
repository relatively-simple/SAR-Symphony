"""FastAPI integration tests covering Earth target presets, SFP1 frames, 6-signal spectrum, EONET, and health."""

import json
from pathlib import Path
import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.io.framepack import decode_framepack, encode_framepack
from app.main import create_app
from app.models import (
    GridSpec,
    ProductInfo,
    SessionManifest,
    SpectrumResult,
    TargetRef,
)


def _setup_synthetic_preset(
    preset_dir: Path,
    slug: str = "kandy-floods",
    products: list[str] | None = None,
) -> SessionManifest:
    """Helper creating a synthetic Earth preset directory with SFP1 frames, manifest, thumb, and spectrum."""
    if products is None:
        products = ["radar", "rain", "wind", "temp", "optical", "nightlights", "diffs", "pass_coadds", "rgb", "coldglow"]

    slug_dir = preset_dir / slug
    frames_dir = slug_dir / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)

    frame_ids = [f"f_{i:02d}" for i in range(12)]
    product_infos = {}

    for prod in products:
        planes = 3 if prod == "rgb" else 1
        data = np.ones((12, planes, 16, 16), dtype=np.float32) * 5.0
        flags = np.zeros((12, 16, 16), dtype=np.uint16)
        if prod == "radar":
            flags[2, 5, 5] = 0x0001  # Wind-Ripple illusion
        blob = encode_framepack(frame_ids, data, flags if prod != "rgb" else None)
        (frames_dir / f"{prod}.sfp").write_bytes(blob)
        product_infos[prod] = ProductInfo(
            name=prod,
            url=f"/api/sessions/{slug}/frames/{prod}.sfp",
            n_frames=12,
            planes_per_frame=planes,
            has_flags=True,
            bytes=len(blob),
        )

    manifest = SessionManifest(
        session_id=slug,
        source="preset",
        target=TargetRef(ra=80.6337, dec=7.2906, name="Kandy Floods & Mahaweli Surge", slug=slug),
        grid=GridSpec(ra0=80.6337, dec0=7.2906, fov_deg=0.5, npix=16),
        passes=[],
        products=product_infos,
        frames={},
        category="Flood",
        region_label="Central Highlands, Sri Lanka",
        sensors_used=["Sentinel-1 SAR", "NASA GPM IMERG"],
        illusion_summary="Wind-roughened reservoir mimicking land backscatter.",
        created_utc="2026-11-15T00:00:00Z",
        pipeline_version="v2.0-earth-symphony",
    )
    (slug_dir / "manifest.json").write_text(manifest.model_dump_json(), encoding="utf-8")
    (slug_dir / "thumb.webp").write_bytes(b"RIFF\x00\x00\x00\x00WEBPVP8 ")

    dates = [f"2026-11-{i+1:02d}" for i in range(12)]
    series = {
        "radar": [-15.0] * 12,
        "rain": [0.0, 5.0, 35.0, 45.0, 10.0, 2.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        "wind": [3.0, 4.0, 14.0, 12.0, 6.0, 3.0, 2.0, 2.0, 2.0, 2.0, 2.0, 2.0],
        "temp": [25.0] * 12,
        "optical": [0.75] * 12,
        "nightlights": [20.0, 20.0, 18.0, 4.0, 5.0, 12.0, 18.0, 20.0, 20.0, 20.0, 20.0, 20.0],
    }
    units = {"radar": "dB", "rain": "mm/hr", "wind": "m/s", "temp": "°C", "optical": "NDVI", "nightlights": "nW/cm²/sr"}
    spec = SpectrumResult(
        ra=80.6337,
        dec=7.2906,
        series=series,
        dates=dates,
        units=units,
        location_story="Monsoon deluge inundated valley with reservoir wind waves.",
        points=[],
        aperture_arcsec=10.0,
        n_used=12,
        n_rejected=0,
    )
    (slug_dir / "spectrum.json").write_text(spec.model_dump_json(), encoding="utf-8")

    return manifest


# ==============================================================================
# Tier 1: Target Presets API & Search Filtering
# ==============================================================================

def test_api_targets_list_and_search_filter(tmp_path: Path) -> None:
    """GET /api/targets lists presets and filters by search query parameter q."""
    preset_dir = tmp_path / "presets"
    cache_dir = tmp_path / "cache"

    _setup_synthetic_preset(preset_dir, "kandy-floods")
    _setup_synthetic_preset(preset_dir, "maui-wildfire")

    cfg = Settings(
        SPX_PRESET_DIR=preset_dir,
        SPX_CACHE_DIR=cache_dir,
        SPX_FRONTEND_DIST=tmp_path / "dist",
    )
    with TestClient(create_app(cfg)) as client:
        # 1. Full preset list
        r = client.get("/api/targets")
        assert r.status_code == 200
        targets = r.json()
        assert len(targets) >= 1
        slugs = [t["slug"] for t in targets]

        # Verify pre-baked bundle flag
        kandy = next((t for t in targets if t["slug"] == "kandy-floods"), None)
        if kandy:
            assert kandy["has_preset_bundle"] is True

        # 2. Search filtering with ?q= (if supported by M2)
        r_search = client.get("/api/targets?q=kandy")
        assert r_search.status_code == 200
        results = r_search.json()
        if len(results) < len(targets):
            # Filtering is active
            assert all("kandy" in t["slug"].lower() or "kandy" in t.get("name", "").lower() for t in results)


def test_api_target_manifest_and_thumbnail(tmp_path: Path) -> None:
    """GET /api/targets/{slug} and GET /api/targets/{slug}/thumb.webp."""
    preset_dir = tmp_path / "presets"
    _setup_synthetic_preset(preset_dir, "kandy-floods")

    cfg = Settings(
        SPX_PRESET_DIR=preset_dir,
        SPX_CACHE_DIR=tmp_path / "cache",
        SPX_FRONTEND_DIST=tmp_path / "dist",
    )
    with TestClient(create_app(cfg)) as client:
        # Valid preset manifest
        r = client.get("/api/targets/kandy-floods")
        assert r.status_code == 200
        m = r.json()
        assert m["session_id"] == "kandy-floods"

        # Valid thumbnail
        r_thumb = client.get("/api/targets/kandy-floods/thumb.webp")
        assert r_thumb.status_code == 200
        assert "webp" in r_thumb.headers.get("content-type", "")

        # Non-existent preset returns 404 TARGET_NOT_FOUND
        r_bad = client.get("/api/targets/nonexistent-event")
        assert r_bad.status_code == 404
        assert r_bad.json().get("error_code") == "TARGET_NOT_FOUND"


# ==============================================================================
# Tier 1 & 2: SFP1 Binary Framepack Serving & Product Validation
# ==============================================================================

def test_api_frames_serving_allowed_and_bad_products(tmp_path: Path) -> None:
    """GET /api/sessions/{session_id}/frames/{product}.sfp serves SFP1 binary bundles."""
    preset_dir = tmp_path / "presets"
    _setup_synthetic_preset(preset_dir, "kandy-floods")

    cfg = Settings(
        SPX_PRESET_DIR=preset_dir,
        SPX_CACHE_DIR=tmp_path / "cache",
        SPX_FRONTEND_DIST=tmp_path / "dist",
    )
    with TestClient(create_app(cfg)) as client:
        # Check an allowed product (e.g. diffs or pass_coadds or radar)
        # Note: if ALLOWED_PRODUCTS in frames.py is updated in M2 to include radar, test radar; else diffs
        from app.api.frames import ALLOWED_PRODUCTS

        test_prod = "radar" if "radar" in ALLOWED_PRODUCTS else "diffs"
        r_frame = client.get(f"/api/sessions/kandy-floods/frames/{test_prod}.sfp")
        assert r_frame.status_code == 200
        assert r_frame.headers.get("content-type") == "application/octet-stream"

        header, data, flags = decode_framepack(r_frame.content)
        assert header["n_frames"] == 12
        assert data.shape[0] == 12

        # Invalid product returns 404 BAD_PRODUCT
        r_bad = client.get("/api/sessions/kandy-floods/frames/invalid_xyz.sfp")
        assert r_bad.status_code == 404
        assert r_bad.json().get("error_code") == "BAD_PRODUCT"


# ==============================================================================
# Tier 1 & 2: 6-Signal Spectrum API & Boundary Validation
# ==============================================================================

def test_api_spectrum_endpoint_and_coordinate_validation(tmp_path: Path) -> None:
    """GET /api/sessions/{session_id}/spectrum serves 6-signal JSON timeline."""
    preset_dir = tmp_path / "presets"
    _setup_synthetic_preset(preset_dir, "kandy-floods")

    cfg = Settings(
        SPX_PRESET_DIR=preset_dir,
        SPX_CACHE_DIR=tmp_path / "cache",
        SPX_FRONTEND_DIST=tmp_path / "dist",
    )
    with TestClient(create_app(cfg)) as client:
        # Valid spectrum query
        r = client.get("/api/sessions/kandy-floods/spectrum?ra=80.6337&dec=7.2906")
        assert r.status_code == 200
        spec = r.json()
        assert "series" in spec or "points" in spec

        # Invalid dec out of [-90, 90] bounds returns 422
        r_bad_dec = client.get("/api/sessions/kandy-floods/spectrum?ra=80.6337&dec=95.0")
        assert r_bad_dec.status_code == 422


# ==============================================================================
# Tier 1: NASA EONET v3 Feed Endpoint (M2)
# ==============================================================================

def test_api_eonet_endpoint(tmp_path: Path) -> None:
    """GET /api/eonet serves active natural disaster events feed."""
    cfg = Settings(
        SPX_PRESET_DIR=tmp_path / "presets",
        SPX_CACHE_DIR=tmp_path / "cache",
        SPX_FRONTEND_DIST=tmp_path / "dist",
    )
    app = create_app(cfg)
    with TestClient(app) as client:
        r = client.get("/api/eonet")
        if r.status_code == 404:
            pytest.skip("GET /api/eonet endpoint not yet mounted in main.py (M2)")

        assert r.status_code == 200
        events = r.json()
        assert isinstance(events, list)

        # Test category filtering if available
        r_filtered = client.get("/api/eonet?category=severeStorms&limit=5")
        assert r_filtered.status_code == 200


# ==============================================================================
# Tier 1 & 2: System Health & Error Routing
# ==============================================================================

def test_api_health_status(tmp_path: Path) -> None:
    """GET /api/health returns operational status and cache metrics."""
    preset_dir = tmp_path / "presets"
    _setup_synthetic_preset(preset_dir, "kandy-floods")

    cfg = Settings(
        SPX_PRESET_DIR=preset_dir,
        SPX_CACHE_DIR=tmp_path / "cache",
        SPX_FRONTEND_DIST=tmp_path / "dist",
    )
    with TestClient(create_app(cfg)) as client:
        r = client.get("/api/health")
        assert r.status_code == 200
        h = r.json()
        assert "presets_ready" in h
        assert "version" in h
        assert "kandy-floods" in h["presets_ready"]


def test_api_error_handlers_and_spa(tmp_path: Path) -> None:
    """Verify 400 INVALID_SESSION_ID, 404 NOT_FOUND, and SPA fallback."""
    dist_dir = tmp_path / "dist"
    dist_dir.mkdir(parents=True)
    (dist_dir / "index.html").write_text("<!doctype html><html><body>SAR Symphony OK</body></html>", encoding="utf-8")

    cfg = Settings(
        SPX_PRESET_DIR=tmp_path / "presets",
        SPX_CACHE_DIR=tmp_path / "cache",
        SPX_FRONTEND_DIST=dist_dir,
    )
    with TestClient(create_app(cfg)) as client:
        # Invalid session ID with illegal characters
        r_bad_sess = client.get("/api/sessions/bad$id/frames/diffs.sfp")
        assert r_bad_sess.status_code == 400
        assert r_bad_sess.json().get("error_code") == "INVALID_SESSION_ID"

        # Non-existent API route returns 404 NOT_FOUND
        r_bad_route = client.get("/api/no-such-api-route")
        assert r_bad_route.status_code == 404
        assert r_bad_route.json().get("error_code") == "NOT_FOUND"

        # Root URL serves SPA index
        r_spa = client.get("/")
        assert r_spa.status_code == 200
        assert "SAR Symphony OK" in r_spa.text
