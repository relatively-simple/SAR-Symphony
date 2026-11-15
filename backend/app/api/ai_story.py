"""Live multi-scale Earth story synthesis, real historical disaster lookup, and 2-tier AI causal endpoints."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
import json
import math
from pathlib import Path
import re
from typing import Any

from astropy.time import Time
from fastapi import APIRouter, Depends, Query
import httpx

from app.config import Settings, get_settings
from app.core.errors import ExploreError
from app.core.presets import PRESETS
from app.io.framepack import encode_framepack
from app.models import (
    AiExplainRequest,
    AiExplainResponse,
    OverlaySet,
    ProductInfo,
    SessionManifest,
    TargetRef,
)
from app.pipeline.session import (
    DEFAULT_CITATIONS,
    find_session_dir,
    load_manifest,
    make_session_id,
    save_manifest,
)
from app.science.ai_director import build_dynamic_story_bundle, explain_event_causality
from app.science.earth_signals import (
    _wrap_signed_lon,
    extract_signal_rhythm_at,
    fetch_asf_sar_metadata,
    fetch_open_meteo_daily,
    generate_multi_sensor_cube,
)

router = APIRouter(prefix="/api", tags=["ai-story"])

_LIVE_LOCKS: dict[str, asyncio.Lock] = {}

_PRESET_SEARCH_ALIASES: list[tuple[tuple[str, ...], str]] = [
    (("kandy", "sri lanka flood", "ditwah", "peradeniya", "mahaweli flood"), "kandy-floods"),
    (("maui", "lahaina"), "maui-wildfire"),
    (("amazon", "manaus", "negro drought"), "amazon-drought-fire"),
    (("mahaweli", "polonnaruwa", "rice", "paddy"), "mahaweli-rice"),
    (("jakobshavn", "ilulissat", "greenland", "sermeq"), "jakobshavn-glacier"),
]

_HISTORICAL_EVENT_CATALOG: list[dict[str, Any]] = [
    {
        "slug": "dubai-flood-2024",
        "keywords": ("dubai", "uae flood", "al ain"),
        "title": "2024 Dubai & UAE Flash Floods",
        "region_label": "Dubai & Northern Emirates, UAE",
        "category": "Flood & Cyclone",
        "lat": 25.2048,
        "lon": 55.2708,
        "upwind_coord": (24.6, 58.9),
        "upwind_label": "Gulf of Oman & Arabian Sea Low",
        "start_date": "2024-04-10",
        "end_date": "2024-04-21",
        "cause": "Cut-off upper atmospheric trough tapped +28.5°C Arabian Sea moisture over the Gulf of Oman, driving a 2-year average rainfall deluge in 24 hours across Dubai.",
        "fallback_temp": [31.2, 32.0, 32.8, 33.4, 29.5, 25.1, 24.4, 26.8, 28.9, 30.4, 31.5, 32.1],
        "fallback_wind": [5.8, 7.2, 10.4, 15.6, 19.2, 21.8, 17.4, 11.2, 8.0, 6.4, 5.5, 5.1],
        "fallback_rain": [0.0, 0.2, 2.5, 18.0, 72.0, 148.0, 64.0, 9.5, 1.2, 0.0, 0.0, 0.0],
    },
    {
        "slug": "valencia-dana-2024",
        "keywords": ("valencia", "spain flood", "dana", "paiporta"),
        "title": "2024 Valencia DANA Flash Floods",
        "region_label": "Valencia & Júcar–Turia Basin, Spain",
        "category": "Flood & Cyclone",
        "lat": 39.4699,
        "lon": -0.3763,
        "upwind_coord": (38.8, 3.1),
        "upwind_label": "Balearic Mediterranean Moisture Plume",
        "start_date": "2024-10-24",
        "end_date": "2024-11-04",
        "cause": "Isolated high-altitude cold drop (DANA) drew anomalous +23.8°C Mediterranean moisture inland into the Turia & Magro escarpment, unloading >450 mm convective rain.",
        "fallback_temp": [22.4, 22.8, 23.1, 21.6, 19.2, 17.8, 18.4, 19.6, 20.5, 21.0, 21.3, 21.5],
        "fallback_wind": [6.1, 8.4, 12.2, 16.8, 19.5, 20.6, 14.3, 9.5, 7.2, 6.0, 5.4, 5.2],
        "fallback_rain": [1.0, 4.5, 19.0, 88.0, 195.0, 162.0, 42.0, 12.0, 3.5, 1.0, 0.4, 0.2],
    },
    {
        "slug": "pakistan-flood-2022",
        "keywords": ("pakistan", "indus", "sindh", "balochistan"),
        "title": "2022 Pakistan Monsoon Mega-Floods",
        "region_label": "Lower Indus & Larkana Basin, Pakistan",
        "category": "Flood & Cyclone",
        "lat": 27.5570,
        "lon": 68.2028,
        "upwind_coord": (23.8, 66.4),
        "upwind_label": "Arabian Sea Monsoon Depression",
        "start_date": "2022-08-14",
        "end_date": "2022-08-25",
        "cause": "Intense +48°C summer land-surface heating over Sindh pulled deep Arabian Sea monsoon depressions inland alongside accelerated glacier melt, submerging the Indus floodplain.",
        "fallback_temp": [41.5, 42.8, 40.2, 36.4, 32.8, 31.0, 31.9, 33.4, 35.1, 36.2, 37.0, 37.5],
        "fallback_wind": [7.5, 9.2, 13.8, 17.4, 18.9, 16.5, 12.8, 9.6, 8.1, 7.2, 6.8, 6.5],
        "fallback_rain": [8.0, 22.0, 68.0, 142.0, 188.0, 155.0, 96.0, 44.0, 18.0, 7.0, 3.0, 1.5],
    },
    {
        "slug": "helene-flood-2024",
        "keywords": ("helene", "asheville", "north carolina", "nc flood", "appalachian"),
        "title": "2024 Hurricane Helene Appalachian Floods",
        "region_label": "Asheville & Blue Ridge, North Carolina",
        "category": "Flood & Cyclone",
        "lat": 35.5951,
        "lon": -82.5515,
        "upwind_coord": (27.4, -84.2),
        "upwind_label": "Gulf Loop Current (+30.5°C)",
        "start_date": "2024-09-21",
        "end_date": "2024-10-02",
        "cause": "Superheated +30.5°C Gulf of Mexico waters fueled rapid Hurricane Helene intensification; a predecessor rainband saturated Blue Ridge slopes before eyewall rainfall hit.",
        "fallback_temp": [26.8, 27.1, 25.9, 23.4, 21.8, 20.5, 20.1, 21.4, 22.8, 23.6, 24.1, 24.5],
        "fallback_wind": [4.8, 6.2, 9.5, 14.2, 21.4, 24.8, 19.6, 11.0, 7.4, 5.8, 4.9, 4.5],
        "fallback_rain": [2.0, 12.0, 58.0, 95.0, 134.0, 176.0, 82.0, 14.0, 3.0, 0.5, 0.2, 0.0],
    },
    {
        "slug": "derna-flood-2023",
        "keywords": ("derna", "libya", "daniel"),
        "title": "2023 Storm Daniel & Derna Flood",
        "region_label": "Derna & Jabal al-Akhdar, Libya",
        "category": "Flood & Cyclone",
        "lat": 32.7670,
        "lon": 22.6367,
        "upwind_coord": (35.8, 19.8),
        "upwind_label": "Central Mediterranean Medicane",
        "start_date": "2023-09-05",
        "end_date": "2023-09-16",
        "cause": "Marine heatwave water in the Ionian Sea energized Medicane Daniel's warm-core spiral, slamming 120+ km/h winds and catastrophic wadi runoff into Derna dams.",
        "fallback_temp": [29.4, 29.8, 29.1, 27.6, 25.0, 23.2, 23.8, 25.5, 26.9, 27.8, 28.4, 28.9],
        "fallback_wind": [7.2, 9.8, 14.5, 19.8, 23.6, 25.2, 17.5, 11.4, 8.2, 6.8, 5.9, 5.4],
        "fallback_rain": [0.0, 1.5, 12.0, 48.0, 115.0, 168.0, 54.0, 6.0, 0.8, 0.0, 0.0, 0.0],
    },
    {
        "slug": "remal-cyclone-2024",
        "keywords": ("remal", "bangladesh", "sundarbans", "khulna"),
        "title": "2024 Cyclone Remal Delta Surge",
        "region_label": "Sundarbans & Khulna Delta, Bangladesh",
        "category": "Flood & Cyclone",
        "lat": 21.9497,
        "lon": 89.1833,
        "upwind_coord": (17.5, 89.6),
        "upwind_label": "Northern Bay of Bengal (+31°C SST)",
        "start_date": "2024-05-21",
        "end_date": "2024-06-01",
        "cause": "+31°C Bay of Bengal surface warmth spun Cyclone Remal northward, stalling for 36 hours over coastal delta embankments with tidal storm surge and torrential bands.",
        "fallback_temp": [34.2, 34.8, 33.9, 31.2, 28.4, 27.1, 27.8, 29.5, 31.2, 32.4, 33.1, 33.6],
        "fallback_wind": [8.1, 11.4, 16.5, 22.8, 27.4, 26.0, 18.2, 12.1, 8.9, 7.5, 6.8, 6.4],
        "fallback_rain": [4.0, 14.0, 45.0, 112.0, 165.0, 148.0, 74.0, 22.0, 8.5, 3.0, 1.5, 0.5],
    },
]

_KNOWN_PLACES: dict[str, tuple[float, float, str]] = {
    "kandy": (7.2906, 80.6337, "Kandy, Sri Lanka"),
    "colombo": (6.9271, 79.8612, "Colombo, Sri Lanka"),
    "mahaweli": (7.7200, 80.8800, "Mahaweli Basin, Sri Lanka"),
    "maui": (20.8783, -156.6825, "Lahaina, Maui, USA"),
    "lahaina": (20.8783, -156.6825, "Lahaina, Maui, USA"),
    "manaus": (-3.1190, -60.0217, "Manaus, Amazonas, Brazil"),
    "amazon": (-3.1190, -60.0217, "Central Amazon Basin, Brazil"),
    "jakobshavn": (69.1667, -49.8333, "Jakobshavn Glacier, Greenland"),
    "ilulissat": (69.2198, -51.0986, "Ilulissat Icefjord, Greenland"),
    "tokyo": (35.6762, 139.6503, "Tokyo, Japan"),
    "miami": (25.7617, -80.1918, "Miami, Florida, USA"),
    "houston": (29.7604, -95.3698, "Houston, Texas, USA"),
    "new york": (40.7128, -74.0060, "New York, USA"),
    "london": (51.5072, -0.1276, "London, UK"),
    "mumbai": (19.0760, 72.8777, "Mumbai, India"),
    "dhaka": (23.8103, 90.4125, "Dhaka, Bangladesh"),
    "manila": (14.5995, 120.9842, "Manila, Philippines"),
    "jakarta": (-6.2088, 106.8456, "Jakarta, Indonesia"),
    "bangkok": (13.7563, 100.5018, "Bangkok, Thailand"),
    "sydney": (-33.8688, 151.2093, "Sydney, Australia"),
    "cairo": (30.0444, 31.2357, "Cairo, Egypt"),
    "nairobi": (-1.2921, 36.8219, "Nairobi, Kenya"),
    "reykjavik": (64.1466, -21.9426, "Reykjavik, Iceland"),
    "seoul": (37.5665, 126.9780, "Seoul, South Korea"),
    "paris": (48.8566, 2.3522, "Paris, France"),
}


def _get_live_lock(key: str) -> asyncio.Lock:
    lock = _LIVE_LOCKS.get(key)
    if lock is None:
        if len(_LIVE_LOCKS) > 128:
            for old_key in list(_LIVE_LOCKS.keys())[:64]:
                if not _LIVE_LOCKS[old_key].locked():
                    _LIVE_LOCKS.pop(old_key, None)
        lock = asyncio.Lock()
        _LIVE_LOCKS[key] = lock
    return lock


def _match_preset_alias(q: str | None) -> str | None:
    if not q:
        return None
    ql = q.strip().lower()
    if ql in PRESETS:
        return ql
    for keywords, slug in _PRESET_SEARCH_ALIASES:
        if any(kw in ql for kw in keywords):
            return slug
    return None


def _match_historical_event(q: str | None) -> dict[str, Any] | None:
    if not q:
        return None
    ql = q.strip().lower()
    for item in _HISTORICAL_EVENT_CATALOG:
        if item["slug"] == ql or any(kw in ql for kw in item["keywords"]):
            return item
    return None


def _date_sequence_12(start_date: str) -> list[str]:
    base = datetime.strptime(start_date[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
    return [(base + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(12)]


async def _fetch_historical_archive_weather(
    lon: float,
    lat: float,
    start_date: str,
    end_date: str,
    fallback: dict[str, Any],
    timeout_s: float = 2.5,
) -> dict[str, Any]:
    """Query Open-Meteo ERA5 Historical Archive for documented event dates, falling back cleanly."""
    try:
        async with httpx.AsyncClient(timeout=timeout_s) as client:
            resp = await client.get(
                "https://archive-api.open-meteo.com/v1/archive",
                params={
                    "latitude": round(lat, 4),
                    "longitude": round(lon, 4),
                    "start_date": start_date,
                    "end_date": end_date,
                    "daily": "temperature_2m_max,precipitation_sum,wind_speed_10m_max",
                    "timezone": "UTC",
                },
            )
            if resp.status_code == 200:
                daily = resp.json().get("daily") or {}
                dates = daily.get("time") or []
                temps = daily.get("temperature_2m_max") or []
                rains = daily.get("precipitation_sum") or []
                winds_kmh = daily.get("wind_speed_10m_max") or []
                if len(dates) >= 12:
                    return {
                        "dates": [str(d)[:10] for d in dates[:12]],
                        "temp": [float(v) if v is not None else fallback["temp"][i] for i, v in enumerate(temps[:12])],
                        "rain": [float(v) if v is not None else fallback["rain"][i] for i, v in enumerate(rains[:12])],
                        "wind": [
                            round(float(v) / 3.6, 2) if v is not None else fallback["wind"][i]
                            for i, v in enumerate(winds_kmh[:12])
                        ],
                    }
    except Exception:
        pass
    return fallback


async def _resolve_place(q: str) -> tuple[float, float, str]:
    """Resolve coordinates or free-text place name using Open-Meteo Geocoding + offline gazetteer."""
    text = q.strip()
    if not text:
        raise ExploreError("BAD_QUERY", "Provide coordinates or an event/place name.", 400)

    m = re.match(r"^\s*([+-]?\d+(?:\.\d+)?)\s*[,\s]\s*([+-]?\d+(?:\.\d+)?)\s*$", text)
    if m:
        lat_v = float(m.group(1))
        lon_v = _wrap_signed_lon(float(m.group(2)))
        if -90.0 <= lat_v <= 90.0:
            return lat_v, lon_v, f"{lat_v:+.2f}°, {lon_v:+.2f}°"

    lowered = text.lower()
    try:
        async with httpx.AsyncClient(timeout=2.5) as client:
            resp = await client.get(
                "https://geocoding-api.open-meteo.com/v1/search",
                params={"name": text, "count": 1, "language": "en", "format": "json"},
            )
            if resp.status_code == 200:
                results = resp.json().get("results") or []
                if results:
                    top = results[0]
                    lat_v = float(top["latitude"])
                    lon_v = _wrap_signed_lon(float(top["longitude"]))
                    parts = [top.get("name"), top.get("admin1"), top.get("country")]
                    label = ", ".join(p for p in parts if p)
                    return lat_v, lon_v, label or text
    except Exception:
        pass

    for key, (lat_v, lon_v, label) in _KNOWN_PLACES.items():
        if key in lowered or lowered in key:
            return lat_v, lon_v, label

    raise ExploreError(
        "PLACE_NOT_FOUND",
        f"Could not resolve '{text}'. Try 'Kandy flood', 'Dubai flood 2024', a city name, or 'lat, lon'.",
        404,
    )


async def _compile_and_save_story_session(
    *,
    settings: Settings,
    session_id: str,
    source: str,
    lon_v: float,
    lat_v: float,
    fov: float,
    resolved_title: str,
    region_label: str,
    category: str | None,
    preset_slug: str | None = None,
    live_weather: dict[str, Any] | None = None,
    sar_meta: list[dict[str, Any]] | None = None,
    upwind_coord: tuple[float, float] | None = None,
    upwind_label: str | None = None,
    historical_cause: str | None = None,
) -> SessionManifest:
    session_dir = settings.spx_cache_dir / "sessions" / session_id
    preset = PRESETS.get(preset_slug) if preset_slug else None

    async with _get_live_lock(session_id):
        manifest_path = session_dir / "manifest.json"
        if manifest_path.exists():
            try:
                existing = SessionManifest.model_validate(json.loads(manifest_path.read_text(encoding="utf-8")))
                if existing.story_scenes and existing.event_dates:
                    return existing
            except Exception:
                pass

        loop = asyncio.get_running_loop()
        compiled_products, passes, grid_spec = await loop.run_in_executor(
            None,
            lambda: generate_multi_sensor_cube(
                lon=lon_v,
                lat=lat_v,
                fov_deg=fov,
                preset_slug=preset_slug,
                npix=64,
                n_frames=12,
                live_weather=live_weather,
                category_hint=category or resolved_title,
            ),
        )

        if preset is not None:
            story_scenes = preset.story_scenes
            geo_features = preset.geo_features
            causal_summary = preset.causal_summary
            illusion_summary = preset.illusion_summary
            cat_display = preset.category
            sensors = preset.sensors_used
            event_dates = preset.event_dates or [Time(p.mjd_mid, format="mjd").iso[:10] for p in passes]
        else:
            (
                story_scenes,
                geo_features,
                causal_summary,
                illusion_summary,
                canonical_cat,
            ) = build_dynamic_story_bundle(
                lon=lon_v,
                lat=lat_v,
                title=resolved_title,
                category_hint=category,
                passes=passes,
                live_weather=live_weather,
                sar_metadata=sar_meta or [],
                upwind_coord=upwind_coord,
                upwind_label=upwind_label,
                historical_cause=historical_cause,
            )
            cat_label_map = {
                "flood": "Flood & Landslide",
                "cyclone": "Cyclone & Monsoon",
                "wildfire": "Wildfire & Heat",
                "glacier": "Cryosphere & Glacier",
                "drought": "Drought & Stress",
                "volcano": "Geohazard",
            }
            cat_display = category.strip() if category else cat_label_map.get(canonical_cat, "Earth Hazard")
            sensors = [
                "NASA MODIS/GHRSST Temp",
                "NASA MERRA-2/ERA5 Wind",
                "NASA GPM IMERG Rain",
                "NASA MODIS/VIIRS Optical",
                "Sentinel-1/NISAR SAR",
                "NASA VIIRS Black Marble",
            ]
            event_dates = (
                list(live_weather["dates"][:12])
                if live_weather and isinstance(live_weather.get("dates"), list) and len(live_weather["dates"]) >= 12
                else ([Time(p.mjd_mid, format="mjd").iso[:10] for p in passes] if passes else [])
            )

        frames_dir = session_dir / "frames"
        frames_dir.mkdir(parents=True, exist_ok=True)
        prod_infos: dict[str, ProductInfo] = {}
        frames_meta: dict[str, list[Any]] = {}

        for name, prod in compiled_products.items():
            blob = encode_framepack(prod.frame_ids, prod.data, prod.flags)
            (frames_dir / f"{name}.sfp").write_bytes(blob)
            prod_infos[name] = ProductInfo(
                name=name,
                url=f"/api/sessions/{session_id}/frames/{name}.sfp",
                n_frames=len(prod.frame_ids),
                planes_per_frame=prod.planes_per_frame,
                has_flags=prod.flags is not None,
                bytes=len(blob),
            )
            frames_meta[name] = prod.metas

        manifest = SessionManifest(
            session_id=session_id,
            source=source,  # type: ignore[arg-type]
            target=TargetRef(
                ra=round(lon_v, 6),
                dec=round(lat_v, 6),
                lon=round(lon_v, 6),
                lat=round(lat_v, 6),
                name=resolved_title,
                slug=preset_slug or session_id,
                mjd_ref=passes[0].mjd_mid if passes else 60997.0,
            ),
            grid=grid_spec,
            passes=passes,
            products=prod_infos,
            frames=frames_meta,
            warnings=[preset.caveat] if (preset and preset.caveat) else [],
            citations=DEFAULT_CITATIONS,
            created_utc=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            pipeline_version=settings.pipeline_version,
            category=cat_display,
            region_label=region_label,
            sensors_used=sensors,
            story_scenes=story_scenes,
            illusion_summary=illusion_summary,
            causal_summary=causal_summary,
            event_dates=event_dates,
            geo_features=geo_features,
        )
        save_manifest(session_dir, manifest)

        spec = extract_signal_rhythm_at(lon_v, lat_v, session_dir, manifest)
        (session_dir / "spectrum.json").write_text(spec.model_dump_json(indent=2), encoding="utf-8")

        overlays = OverlaySet(
            gaia=[],
            allwise=[],
            source="preset" if preset_slug else "live",
            mjd_ref=2026.0,
            note=f"Earth domino hazard bundle for {resolved_title}",
        )
        (session_dir / "overlays.json").write_text(overlays.model_dump_json(indent=2), encoding="utf-8")
        return manifest


@router.get("/story/live", response_model=SessionManifest)
async def get_live_story(
    q: str | None = Query(None, description="Event name (e.g. 'Kandy flood', 'Dubai flood 2024'), city, or 'lat, lon'"),
    lat: float | None = Query(None, ge=-90.0, le=90.0),
    lon: float | None = Query(None, ge=-360.0, le=360.0),
    title: str | None = Query(None),
    category: str | None = Query(None),
    fov: float = Query(0.5, gt=0.01, le=5.0),
    settings: Settings = Depends(get_settings),
) -> SessionManifest:
    """Resolve a searched historical disaster, flagship preset, or live EONET/city event into a 5-step domino story."""
    # 1. Exact Flagship Preset match on search string (unless explicit lat/lon override)
    if (lat is None or lon is None) and q:
        matched_preset = _match_preset_alias(q)
        if matched_preset:
            try:
                return load_manifest(settings, matched_preset)
            except Exception:
                # Preset directory not populated (e.g. isolated test tmp_path): compile preset directly
                p = PRESETS[matched_preset]
                return await _compile_and_save_story_session(
                    settings=settings,
                    session_id=matched_preset,
                    source="preset",
                    lon_v=_wrap_signed_lon(p.lon),
                    lat_v=p.lat,
                    fov=p.default_fov,
                    resolved_title=p.name,
                    region_label=p.region_label,
                    category=p.category,
                    preset_slug=matched_preset,
                )

    # 2. Documented Historical Event Catalog match (real historical dates + real upwind cause corridor)
    hist_match = _match_historical_event(q or title) if (lat is None or lon is None) else None
    if hist_match is not None:
        lat_v = float(hist_match["lat"])
        lon_v = _wrap_signed_lon(float(hist_match["lon"]))
        resolved_title = hist_match["title"]
        region_label = hist_match["region_label"]
        cat_arg = hist_match["category"]
        fallback_w = {
            "dates": _date_sequence_12(hist_match["start_date"]),
            "temp": list(hist_match["fallback_temp"]),
            "wind": list(hist_match["fallback_wind"]),
            "rain": list(hist_match["fallback_rain"]),
        }
        weather_task = _fetch_historical_archive_weather(
            lon_v,
            lat_v,
            hist_match["start_date"],
            hist_match["end_date"],
            fallback_w,
            timeout_s=2.5,
        )
        asf_task = fetch_asf_sar_metadata(lon=lon_v, lat=lat_v, timeout_s=2.5)
        weather_res, asf_res = await asyncio.gather(weather_task, asf_task, return_exceptions=True)
        live_weather = weather_res if isinstance(weather_res, dict) else fallback_w
        sar_meta = asf_res if isinstance(asf_res, list) else []
        return await _compile_and_save_story_session(
            settings=settings,
            session_id=hist_match["slug"],
            source="live",
            lon_v=lon_v,
            lat_v=lat_v,
            fov=fov,
            resolved_title=resolved_title,
            region_label=region_label,
            category=cat_arg,
            live_weather=live_weather,
            sar_meta=sar_meta,
            upwind_coord=hist_match["upwind_coord"],
            upwind_label=hist_match["upwind_label"],
            historical_cause=hist_match["cause"],
        )

    # 3. Direct coordinates (e.g. NASA EONET event click) or Open-Meteo city geocoding
    if lat is not None and lon is not None:
        if not (math.isfinite(lat) and math.isfinite(lon)):
            raise ExploreError("BAD_COORDS", "Latitude and longitude must be finite numbers.", 400)
        lat_v = float(lat)
        lon_v = _wrap_signed_lon(float(lon))
        resolved_title = (title or q or f"Earth Event ({lat_v:+.2f}°, {lon_v:+.2f}°)").strip()
        region_label = f"{lat_v:+.2f}°, {lon_v:+.2f}°"
    elif q is not None and q.strip():
        lat_v, lon_v, resolved_label = await _resolve_place(q)
        resolved_title = (title or resolved_label).strip()
        region_label = resolved_label
    else:
        raise ExploreError("MISSING_LOCATION", "Provide either 'lat' + 'lon' or 'q' event/place query.", 400)

    weather_task = fetch_open_meteo_daily(lon=lon_v, lat=lat_v, timeout_s=2.5)
    asf_task = fetch_asf_sar_metadata(lon=lon_v, lat=lat_v, timeout_s=2.5)
    weather_res, asf_res = await asyncio.gather(weather_task, asf_task, return_exceptions=True)

    live_weather = weather_res if isinstance(weather_res, dict) and weather_res.get("dates") else None
    sar_meta = asf_res if isinstance(asf_res, list) else []

    tag_slug = re.sub(r"[^a-z0-9]+", "-", resolved_title.lower()).strip("-")[:20] or "live"
    cat_tag = re.sub(r"[^a-z0-9]+", "-", (category or "auto").lower()).strip("-")[:16] or "auto"
    session_id = make_session_id(
        lon_v,
        lat_v,
        fov,
        [f"live:{cat_tag}:{tag_slug}"],
        settings.pipeline_version,
    )
    return await _compile_and_save_story_session(
        settings=settings,
        session_id=session_id,
        source="live",
        lon_v=lon_v,
        lat_v=lat_v,
        fov=fov,
        resolved_title=resolved_title,
        region_label=region_label,
        category=category,
        live_weather=live_weather,
        sar_meta=sar_meta,
    )


@router.post("/ai/explain", response_model=AiExplainResponse)
async def post_ai_explain(
    req: AiExplainRequest,
    settings: Settings = Depends(get_settings),
) -> AiExplainResponse:
    """Run the 2-Tier AI Causal Director over a session's spatio-temporal signals."""
    session_id = (req.session_id or "kandy-floods").strip() or "kandy-floods"
    manifest = load_manifest(settings, session_id)
    session_dir = find_session_dir(settings, session_id)

    if req.lat is not None and req.lon is not None:
        spec = extract_signal_rhythm_at(_wrap_signed_lon(req.lon), req.lat, session_dir, manifest)
    else:
        spec_path = session_dir / "spectrum.json"
        if spec_path.exists():
            try:
                from app.models import SpectrumResult

                spec = SpectrumResult.model_validate(json.loads(spec_path.read_text(encoding="utf-8")))
            except Exception:
                spec = extract_signal_rhythm_at(manifest.grid.ra0, manifest.grid.dec0, session_dir, manifest)
        else:
            spec = extract_signal_rhythm_at(manifest.grid.ra0, manifest.grid.dec0, session_dir, manifest)

    return await explain_event_causality(req, manifest, spec)
