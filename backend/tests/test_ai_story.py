"""Tests for multi-scale flagship presets, /api/story/live, and /api/ai/explain."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.config import Settings
from app.core.presets import FLAGSHIP_PRESETS, PRESETS
from app.main import create_app


def _make_client(tmp_path: Path) -> TestClient:
    preset_dir = tmp_path / "presets"
    cache_dir = tmp_path / "cache"
    preset_dir.mkdir(parents=True, exist_ok=True)
    cache_dir.mkdir(parents=True, exist_ok=True)
    settings = Settings(
        spx_preset_dir=preset_dir,
        spx_cache_dir=cache_dir,
        spx_frontend_dist=tmp_path / "no-dist",
    )
    app = create_app(settings=settings)
    return TestClient(app)


def test_presets_have_authentic_dates_signed_lons_and_multiscale_scenes() -> None:
    """Verify each flagship preset has distinct event_dates, signed lon, 5 cameras, and geo_features."""
    seen_start_dates: set[str] = set()
    for slug in FLAGSHIP_PRESETS:
        preset = PRESETS[slug]
        assert -180.0 <= preset.lon <= 180.0
        assert -90.0 <= preset.lat <= 90.0
        assert len(preset.event_dates) == 12
        seen_start_dates.add(preset.event_dates[0])
        assert preset.causal_summary
        assert len(preset.geo_features) >= 2
        assert len(preset.story_scenes) == 5
        for scene in preset.story_scenes:
            assert scene.camera is not None
            assert scene.camera.zoom >= 4.0
            assert len(scene.causal_chain) >= 1
            assert scene.gibs_layer
            assert scene.gibs_date

    # All 5 flagship events must span distinct event dates (never hardcoded identical dates)
    assert len(seen_start_dates) == len(FLAGSHIP_PRESETS)


def test_live_story_endpoint_by_coords_and_place(tmp_path: Path) -> None:
    """GET /api/story/live builds a complete 5-scene signed-longitude session manifest."""
    client = _make_client(tmp_path)

    resp_coords = client.get(
        "/api/story/live",
        params={"lat": 7.2906, "lon": 80.6337, "title": "Kandy Live Check", "category": "Floods"},
    )
    assert resp_coords.status_code == 200
    m1 = resp_coords.json()
    assert len(m1["story_scenes"]) == 5
    assert len(m1["geo_features"]) >= 4
    assert m1["causal_summary"]
    assert -180.0 <= m1["target"]["lon"] <= 180.0
    assert -180.0 <= m1["grid"]["ra0"] <= 180.0
    assert len(m1["event_dates"]) == 12
    assert m1["story_scenes"][0]["camera"]["zoom"] < m1["story_scenes"][2]["camera"]["zoom"]

    resp_city = client.get("/api/story/live", params={"q": "Miami"})
    assert resp_city.status_code == 200
    m2 = resp_city.json()
    assert -180.0 <= m2["target"]["lon"] <= 0.0  # Western hemisphere must stay negative
    assert len(m2["story_scenes"]) == 5

    # Preset alias search ("Kandy flood") must resolve to curated kandy-floods manifest
    resp_kandy = client.get("/api/story/live", params={"q": "Kandy flood"})
    assert resp_kandy.status_code == 200
    m_kandy = resp_kandy.json()
    assert m_kandy["session_id"] == "kandy-floods"
    assert m_kandy["event_dates"][0].startswith("2024-11")

    # Documented historical event search ("Dubai flood 2024") returns April 2024 dates & upwind origin
    resp_dubai = client.get("/api/story/live", params={"q": "Dubai flood 2024"})
    assert resp_dubai.status_code == 200
    m_dubai = resp_dubai.json()
    assert m_dubai["event_dates"][0] == "2024-04-10"
    assert "Gulf of Oman" in m_dubai["story_scenes"][0]["camera"]["region_name"]
    assert len(m_dubai["story_scenes"]) == 5

    # Follow-up AI Causal Explanation against the live session
    ai_resp = client.post(
        "/api/ai/explain",
        json={
            "session_id": m1["session_id"],
            "question": "Why did wind and rain precede the SAR flood and nightlight drop?",
            "scene_index": 3,
            "lat": 7.2906,
            "lon": 80.6337,
            "illusion_guard": True,
        },
    )
    assert ai_resp.status_code == 200
    ai_data = ai_resp.json()
    assert ai_data["answer"]
    assert ai_data["mode"] in ("causal_graph", "gemini_enhanced")
    assert len(ai_data["recommended_layers"]) >= 1
    assert len(ai_data["key_connections"]) >= 1
    assert ai_data["lead_lag_summary"]
