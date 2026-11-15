"""Multi-Sensor Earth Observation Cube Engine & Live Ingestion for Dancing with the SARs.

Ingests and synthesizes 6 NASA and partner signals:
  1. radar: Sentinel-1 / NISAR / RCM SAR backscatter (dB)
  2. rain: NASA GPM IMERG precipitation rate (mm/hr)
  3. wind: NASA MERRA-2 / CYGNSS surface wind speed (m/s)
  4. temp: MODIS / ECOSTRESS Land Surface Temperature (°C)
  5. optical: Sentinel-2 / VIIRS surface reflectance & NDVI
  6. nightlights: NASA Black Marble (VNP46A2) nocturnal radiance (nW/cm²/sr)

Encodes 10 SFP1 framepacks (radar, rain, wind, temp, optical, nightlights, pass_coadds, diffs, rgb, coldglow)
with uint16 Earth illusion bitmasks (Wind-Ripple, Sub-Zero Freeze, Steep-Slope, Cloud Cover).
Provides extract_signal_rhythm_at() for per-pixel 6-signal time series and location stories.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
import json
import math
from pathlib import Path
from typing import Any

from astropy.wcs import WCS
import httpx
import numpy as np

from app.core.flags import (
    FLAG_CLOUD_COVER,
    FLAG_STEEP_SLOPE,
    FLAG_SUBZERO_FREEZE,
    FLAG_WIND_RIPPLE,
    summarize_uint16_flags,
)
from app.io.framepack import decode_framepack
from app.models import (
    FrameMeta,
    GridSpec,
    ProductInfo,
    SessionManifest,
    SignalId,
    SpectrumPoint,
    SpectrumResult,
    StretchHint,
    SurveyPass,
    TargetRef,
)
from app.science.products import CompiledProduct, compute_stretch_hint


SIGNAL_UNITS: dict[SignalId, str] = {
    "radar": "dB",
    "rain": "mm/hr",
    "wind": "m/s",
    "temp": "°C",
    "optical": "NDVI",
    "nightlights": "nW/cm²/sr",
}

ALL_SIGNAL_IDS: list[SignalId] = ["radar", "rain", "wind", "temp", "optical", "nightlights"]
ALL_PRODUCT_NAMES: list[str] = [
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


def _wrap_signed_lon(lon: float) -> float:
    """Normalize any longitude cleanly to signed geographic [-180, 180]."""
    val = ((float(lon) + 180.0) % 360.0) - 180.0
    if val == -180.0 and float(lon) > 0:
        return 180.0
    return val


def _wcs_from_grid(grid: GridSpec) -> WCS:
    """Create North-Up TAN WCS for coordinate reprojection."""
    cdelt_deg = grid.pixscale_arcsec / 3600.0
    w = WCS(naxis=2)
    w.wcs.ctype = list(grid.ctype)
    w.wcs.crval = [grid.ra0, grid.dec0]
    w.wcs.crpix = [(grid.npix + 1) / 2.0, (grid.npix + 1) / 2.0]
    w.wcs.cdelt = [-cdelt_deg, cdelt_deg]
    return w


def _wcs_from_manifest(manifest: SessionManifest) -> WCS:
    """Reconstruct North-Up TAN WCS from session manifest."""
    return _wcs_from_grid(manifest.grid)


# -----------------------------------------------------------------------------
# NASA & Partner Public API Clients (ASF, GIBS, POWER, EONET)
# -----------------------------------------------------------------------------

async def fetch_asf_sar_metadata(lon: float, lat: float, timeout_s: float = 3.0) -> list[dict]:
    """Query Alaska Satellite Facility (ASF) Search API for Sentinel-1 / NISAR coverage."""
    url = "https://api.daac.asf.alaska.edu/services/search/param"
    params = {
        "intersectsWith": f"POINT({lon:.4f} {lat:.4f})",
        "platform": "SENTINEL-1",
        "processingLevel": "GRD_HD",
        "output": "json",
        "maxResults": "5",
    }
    try:
        async with httpx.AsyncClient(timeout=timeout_s) as client:
            resp = await client.get(url, params=params)
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, list) and data and isinstance(data[0], list):
                    return data[0]
                elif isinstance(data, list):
                    return data
    except Exception:
        pass
    return []


async def fetch_nasa_power_daily(lon: float, lat: float, start_date: str, end_date: str, timeout_s: float = 3.0) -> dict:
    """Query NASA POWER Daily Point API for surface wind (WS10M), precipitation (PRECTOTCORR), and temperature (T2M)."""
    url = "https://power.larc.nasa.gov/api/temporal/daily/point"
    params = {
        "parameters": "T2M,WS10M,PRECTOTCORR",
        "community": "RE",
        "longitude": f"{lon:.4f}",
        "latitude": f"{lat:.4f}",
        "start": start_date.replace("-", ""),
        "end": end_date.replace("-", ""),
        "format": "JSON",
    }
    try:
        async with httpx.AsyncClient(timeout=timeout_s) as client:
            resp = await client.get(url, params=params)
            if resp.status_code == 200:
                data = resp.json()
                return data.get("properties", {}).get("parameter", {})
    except Exception:
        pass
    return {}


async def fetch_open_meteo_daily(lon: float, lat: float, timeout_s: float = 2.5) -> dict[str, list[float]]:
    """Query free public Open-Meteo API (no API key) for 12-day precip, wind, temp, and pressure."""
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": f"{lat:.4f}",
        "longitude": f"{_wrap_signed_lon(lon):.4f}",
        "daily": "temperature_2m_max,precipitation_sum,wind_speed_10m_max",
        "hourly": "surface_pressure",
        "past_days": "10",
        "forecast_days": "2",
        "timezone": "UTC",
    }
    try:
        async with httpx.AsyncClient(timeout=timeout_s) as client:
            resp = await client.get(url, params=params)
            if resp.status_code == 200:
                payload = resp.json()
                daily = payload.get("daily", {})
                dates = daily.get("time", [])[:12]
                temp = [float(x) if x is not None else 25.0 for x in daily.get("temperature_2m_max", [])[:12]]
                rain = [float(x) / 3.0 if x is not None else 0.0 for x in daily.get("precipitation_sum", [])[:12]]
                wind = [float(x) / 3.6 if x is not None else 5.0 for x in daily.get("wind_speed_10m_max", [])[:12]]
                if dates and len(dates) >= 6:
                    return {"dates": dates, "temp": temp, "rain": rain, "wind": wind}
    except Exception:
        pass
    return {}


async def fetch_nasa_eonet_events(lon: float, lat: float, radius_km: float = 300.0, timeout_s: float = 3.0) -> list[dict]:
    """Query NASA EONET v3 for active natural events around coordinates."""
    url = "https://eonet.gsfc.nasa.gov/api/v3/events"
    params = {
        "status": "all",
        "limit": "10",
    }
    try:
        async with httpx.AsyncClient(timeout=timeout_s) as client:
            resp = await client.get(url, params=params)
            if resp.status_code == 200:
                events = resp.json().get("events", [])
                nearby = []
                for ev in events:
                    for geom in ev.get("geometry", []):
                        coords = geom.get("coordinates", [])
                        if len(coords) >= 2:
                            ev_lon, ev_lat = float(coords[0]), float(coords[1])
                            d_deg = math.hypot((ev_lon - lon) * math.cos(math.radians(lat)), ev_lat - lat)
                            if d_deg * 111.0 <= radius_km:
                                nearby.append(ev)
                                break
                return nearby
    except Exception:
        pass
    return []


# -----------------------------------------------------------------------------
# Deterministic Physics-Grounded Spatial & Temporal Simulation Engine
# -----------------------------------------------------------------------------

def _generate_preset_physics(
    preset_slug: str,
    npix: int = 64,
    n_frames: int = 12,
    live_weather: dict[str, Any] | None = None,
    category_hint: str | None = None,
) -> tuple[dict[str, np.ndarray], np.ndarray, list[str]]:
    """Synthesize physically realistic, spatially coherent multi-sensor cubes for flagship presets."""
    from app.core.presets import PRESETS

    yy, xx = np.mgrid[0:npix, 0:npix]
    y_norm = (yy - npix / 2.0) / (npix / 2.0)
    x_norm = (xx - npix / 2.0) / (npix / 2.0)
    dist_center = np.sqrt(x_norm**2 + y_norm**2)

    # Use authentic event-specific dates from preset definition or live weather API (never hardcode Kandy onto other events!)
    base_dates: list[str] = []
    preset_obj = PRESETS.get(preset_slug)
    if preset_obj and preset_obj.event_dates and len(preset_obj.event_dates) >= n_frames:
        base_dates = [f"{d} 06:00 UTC" for d in preset_obj.event_dates[:n_frames]]
    elif live_weather and isinstance(live_weather.get("dates"), list) and len(live_weather["dates"]) >= n_frames:
        base_dates = [f"{d} 06:00 UTC" for d in live_weather["dates"][:n_frames]]
    else:
        start_dt = datetime.now(timezone.utc) - timedelta(days=n_frames - 1)
        for t in range(n_frames):
            dt = start_dt + timedelta(days=t)
            base_dates.append(dt.strftime("%Y-%m-%d 06:00 UTC"))

    signals: dict[str, np.ndarray] = {
        "radar": np.zeros((n_frames, npix, npix), dtype=np.float32),
        "rain": np.zeros((n_frames, npix, npix), dtype=np.float32),
        "wind": np.zeros((n_frames, npix, npix), dtype=np.float32),
        "temp": np.zeros((n_frames, npix, npix), dtype=np.float32),
        "optical": np.zeros((n_frames, npix, npix), dtype=np.float32),
        "nightlights": np.zeros((n_frames, npix, npix), dtype=np.float32),
    }
    flags = np.zeros((n_frames, npix, npix), dtype=np.uint16)

    if preset_slug == "kandy-floods":
        # Terrain: winding Mahaweli River valley running SW-to-NE, Victoria reservoir in east, mountainous slopes
        river_curve = 0.3 * np.sin(x_norm * 3.0)
        river_mask = np.abs(y_norm - river_curve) < 0.12
        reservoir_mask = (x_norm > 0.15) & (y_norm > -0.2) & (y_norm < 0.45)
        water_body = river_mask | reservoir_mask
        mountain_relief = 1.0 - np.clip(np.abs(y_norm - 0.5), 0.0, 1.0) * 0.5
        urban_mask = (x_norm > -0.45) & (x_norm < -0.05) & (y_norm > -0.3) & (y_norm < 0.2)

        for t in range(n_frames):
            # Storm surge profile peaking at t=4..7
            rain_pulse = float(np.exp(-0.5 * ((t - 3.5) / 1.5) ** 2))
            flood_pulse = float(np.exp(-0.5 * ((t - 6.0) / 2.0) ** 2))
            wind_pulse = float(np.exp(-0.5 * ((t - 4.5) / 1.2) ** 2))

            # Rain: IMERG mm/hr
            rain_field = np.clip(rain_pulse * 48.0 * (1.0 + 0.2 * np.sin(xx * 0.1)), 0.0, 65.0)
            signals["rain"][t] = rain_field.astype(np.float32)

            # Wind: MERRA-2 m/s
            wind_speed = 3.5 + wind_pulse * 12.5 + 1.2 * np.cos(yy * 0.08)
            signals["wind"][t] = wind_speed.astype(np.float32)

            # Temp: MODIS LST (°C)
            signals["temp"][t] = (24.0 - rain_pulse * 5.0 + 0.8 * y_norm).astype(np.float32)

            # Optical: NDVI obscured by clouds during storm
            cloud_mask = rain_field > 14.0
            optical_field = np.where(water_body, 0.02, 0.72 - flood_pulse * 0.35 * (dist_center < 0.5))
            signals["optical"][t] = optical_field.astype(np.float32)

            # Nightlights: NASA Black Marble (nW/cm²/sr), plunging during flood peak (grid blackout)
            urban_lights = np.where(urban_mask, 42.0, 2.5)
            blackout_factor = 1.0 - (0.80 * flood_pulse if t >= 4 else 0.0)
            signals["nightlights"][t] = (urban_lights * blackout_factor + 0.5 * np.random.uniform(0.9, 1.1, (npix, npix))).astype(np.float32)

            # Radar: Sentinel-1 backscatter (dB)
            # Baseline: Water = -22 dB (specular), Forest = -9 dB, Urban = -4 dB
            base_sar = np.where(water_body, -22.0, -9.0 + 5.0 * urban_mask)
            # Flood expansion in valley
            flooded_area = (np.abs(y_norm - river_curve) < (0.12 + 0.28 * flood_pulse)) & (dist_center < 0.6)
            sar_val = np.where(flooded_area, -24.0, base_sar)

            # Wind-Ripple Illusion over Victoria Reservoir on days with wind > 7 m/s (peaks at t=4)
            wind_ripple_active = (signals["wind"][t] > 7.5) & reservoir_mask
            sar_val[wind_ripple_active] += 13.5  # Spikes to -8.5 dB (mimicking land!)
            signals["radar"][t] = sar_val.astype(np.float32)

            # Flags
            step_flags = np.zeros((npix, npix), dtype=np.uint16)
            step_flags[wind_ripple_active] |= FLAG_WIND_RIPPLE
            step_flags[cloud_mask] |= FLAG_CLOUD_COVER
            step_flags[mountain_relief > 0.8] |= FLAG_STEEP_SLOPE
            flags[t] = step_flags

    elif preset_slug == "amazon-drought-fire":
        # Amazon basin: river in north, deep canopy, fire front igniting and smoke plume
        river_mask = (y_norm > 0.42) & (y_norm < 0.58)
        forest_mask = ~river_mask
        fire_origin = (x_norm > -0.2) & (x_norm < 0.3) & (y_norm > -0.3) & (y_norm < 0.2)

        for t in range(n_frames):
            drought_prog = float(t / (n_frames - 1.0))
            fire_intensity = float(np.exp(-0.5 * ((t - 8.0) / 1.8) ** 2)) if t >= 5 else 0.0

            signals["rain"][t] = np.clip(1.5 - drought_prog * 1.2 + 0.2 * np.sin(xx), 0.0, 5.0).astype(np.float32)
            signals["wind"][t] = (4.5 + drought_prog * 6.5 + 1.0 * np.sin(yy * 0.1)).astype(np.float32)
            signals["temp"][t] = (27.0 + drought_prog * 11.0 + fire_intensity * 18.0 * fire_origin).astype(np.float32)

            # Optical NDVI: healthy canopy (0.82) drying to 0.55, charred to 0.18
            ndvi = np.where(river_mask, 0.05, 0.82 - drought_prog * 0.22)
            if t >= 8:
                ndvi[fire_origin] = 0.16  # Burn scar
            signals["optical"][t] = ndvi.astype(np.float32)

            # Nightlights: background dark, fire front glows at night!
            nl = np.where(river_mask, 0.2, 0.8)
            nl[fire_origin] += fire_intensity * 38.0
            signals["nightlights"][t] = nl.astype(np.float32)

            # Radar: Dielectric drying illusion (drops 4 dB without trees felled)
            dielectric_loss = drought_prog * 4.5
            sar = np.where(river_mask, -21.0, -7.5 - dielectric_loss)
            if t >= 9:
                sar[fire_origin] -= 3.0  # Structural burn loss
            signals["radar"][t] = sar.astype(np.float32)

            # Flags
            step_flags = np.zeros((npix, npix), dtype=np.uint16)
            if t >= 6:
                step_flags[fire_origin] |= FLAG_CLOUD_COVER  # Thick smoke plume blinds optical
            flags[t] = step_flags

    elif preset_slug == "mahaweli-rice":
        # Agricultural rice grid: square fields with canal dividers
        grid_x = np.floor((x_norm + 1.0) * 4.0) % 2 == 0
        grid_y = np.floor((y_norm + 1.0) * 4.0) % 2 == 0
        paddy_cells = grid_x ^ grid_y

        for t in range(n_frames):
            # Phenology cycle:
            # t=0..2: Tillage (bare soil, radar -14 dB, optical 0.2)
            # t=3..5: Flooding (specular water, radar -23 dB)
            # t=6..8: Emergence & Double-Bounce (radar jumps to +2 dB, optical 0.55)
            # t=9..10: Heading Canopy (optical 0.82, radar -10 dB)
            # t=11: Drainage & Harvest (radar -13 dB, optical 0.35)
            if t <= 2:
                sar_val = -14.0
                ndvi_val = 0.22
                flood_val = 0.0
            elif t <= 5:
                sar_val = -22.5  # Specular flooded mirror
                ndvi_val = 0.30
                flood_val = 1.0
            elif t <= 8:
                sar_val = +2.2   # Double-bounce corner reflection!
                ndvi_val = 0.62
                flood_val = 0.6
            elif t <= 10:
                sar_val = -9.5   # Full volume canopy
                ndvi_val = 0.84
                flood_val = 0.1
            else:
                sar_val = -13.0  # Harvested stubble
                ndvi_val = 0.38
                flood_val = 0.0

            signals["radar"][t] = np.where(paddy_cells, sar_val + 0.8 * np.sin(xx * 0.2), -12.0).astype(np.float32)
            signals["rain"][t] = np.clip(12.0 * flood_val + 1.5 * np.cos(yy), 0.0, 25.0).astype(np.float32)
            signals["wind"][t] = (4.0 + 1.2 * np.sin(xx * 0.1)).astype(np.float32)
            signals["temp"][t] = (29.0 - 2.5 * flood_val + 1.0 * y_norm).astype(np.float32)
            signals["optical"][t] = np.where(paddy_cells, ndvi_val, 0.45).astype(np.float32)
            signals["nightlights"][t] = (3.5 + 1.0 * np.sin(yy * 0.1)).astype(np.float32)

            step_flags = np.zeros((npix, npix), dtype=np.uint16)
            if 3 <= t <= 5:
                step_flags[paddy_cells] |= FLAG_WIND_RIPPLE  # Shallow water surface
            flags[t] = step_flags

    elif preset_slug == "jakobshavn-glacier":
        # Glacial fjord: ice sheet on east, fjord water in center/west, steep rocky cliffs on north/south
        cliff_north = y_norm > 0.45
        cliff_south = y_norm < -0.45
        cliffs = cliff_north | cliff_south
        ice_tongue = (x_norm > -0.2) & (~cliffs)
        calving_front = (x_norm > -0.2) & (x_norm < 0.0) & (~cliffs)

        for t in range(n_frames):
            temp_profile = 2.5 - float(t * 1.5)  # Drops from +2.5°C down to -14°C (Freeze!)
            signals["temp"][t] = (temp_profile + 1.5 * x_norm).astype(np.float32)
            signals["wind"][t] = (8.5 + 4.0 * np.sin(t * 0.6) + 1.2 * y_norm).astype(np.float32)
            signals["rain"][t] = np.clip(1.0 - t * 0.1, 0.0, 3.0).astype(np.float32)
            signals["optical"][t] = np.where(ice_tongue, 0.68, 0.08).astype(np.float32)
            signals["nightlights"][t] = np.full((npix, npix), 0.3, dtype=np.float32)

            # Sub-zero freeze drops dielectric constant, causing backscatter to drop 8 dB
            freeze_drop = 8.5 if temp_profile < 0.0 else 0.0
            # Terminus retreats at t=4
            retreated = calving_front & (t >= 4)
            sar = np.where(cliffs, -4.0, np.where(ice_tongue & ~retreated, -11.0 - freeze_drop, -21.0))
            signals["radar"][t] = sar.astype(np.float32)

            step_flags = np.zeros((npix, npix), dtype=np.uint16)
            step_flags[cliffs] |= FLAG_STEEP_SLOPE  # Fjord cliffs cause layover / shadow
            if temp_profile < 0.0:
                step_flags[ice_tongue] |= FLAG_SUBZERO_FREEZE  # Sub-zero freeze illusion
            flags[t] = step_flags

    elif preset_slug == "maui-wildfire":
        # Lahaina, Maui: ocean on west (x_norm < -0.2), coastal urban town (-0.2 < x_norm < 0.2), steep mountains (x_norm > 0.2)
        ocean_mask = x_norm < -0.25
        town_mask = (x_norm >= -0.25) & (x_norm <= 0.2) & (np.abs(y_norm) < 0.4)
        mountain_mask = x_norm > 0.25

        for t in range(n_frames):
            # Downslope gale peaking at t=2..4
            gale_pulse = float(np.exp(-0.5 * ((t - 2.5) / 1.0) ** 2))
            fire_pulse = float(np.exp(-0.5 * ((t - 5.0) / 1.5) ** 2)) if t >= 3 else 0.0

            wind_speed = 7.0 + gale_pulse * 28.0 + 2.0 * np.sin(yy * 0.1)
            signals["wind"][t] = wind_speed.astype(np.float32)
            signals["rain"][t] = np.zeros((npix, npix), dtype=np.float32)
            signals["temp"][t] = (26.0 + gale_pulse * 4.0 + fire_pulse * 32.0 * town_mask).astype(np.float32)

            # Nightlights: Town starts at 48 nW/cm²/sr, plunges to 4 nW at t=4 (Blackout!)
            base_nl = np.where(town_mask, 52.0, np.where(ocean_mask, 0.1, 1.2))
            if t >= 4:
                base_nl = np.where(town_mask, 4.8, base_nl)
            signals["nightlights"][t] = base_nl.astype(np.float32)

            # Optical: NDVI normal, then obscured by smoke plume, then charred
            ndvi = np.where(ocean_mask, -0.1, np.where(town_mask, 0.35, 0.65))
            if t >= 6:
                ndvi[town_mask] = 0.12  # Burn scar
            signals["optical"][t] = ndvi.astype(np.float32)

            # Radar: Ocean is calm (-23 dB) then choppy during gale (-10 dB, wind-ripple illusion!)
            ocean_sar = -22.0 + (gale_pulse * 12.0 if wind_speed.mean() > 7.0 else 0.0)
            town_sar = -4.0 - (fire_pulse * 5.0 if t >= 6 else 0.0)  # Structural collapse lowers corner returns
            sar = np.where(ocean_mask, ocean_sar, np.where(town_mask, town_sar, -8.0))
            signals["radar"][t] = sar.astype(np.float32)

            step_flags = np.zeros((npix, npix), dtype=np.uint16)
            step_flags[mountain_mask] |= FLAG_STEEP_SLOPE
            if gale_pulse > 0.4:
                step_flags[ocean_mask] |= FLAG_WIND_RIPPLE
            if fire_pulse > 0.3:
                step_flags[town_mask] |= FLAG_CLOUD_COVER  # Thick smoke plume
            flags[t] = step_flags

    else:
        # Dynamic coordinate / EONET event synthesis informed by live weather & hazard category
        rng = np.random.default_rng(abs(hash(f"{preset_slug}:{category_hint}")) % (2**31))
        cat = (category_hint or "floods").lower()
        w_rain = live_weather.get("rain") if isinstance(live_weather, dict) else None
        w_wind = live_weather.get("wind") if isinstance(live_weather, dict) else None
        w_temp = live_weather.get("temp") if isinstance(live_weather, dict) else None

        river_band = np.abs(y_norm - 0.25 * np.sin(x_norm * 2.6)) < 0.14
        town_zone = (np.abs(x_norm + 0.1) < 0.28) & (np.abs(y_norm - 0.1) < 0.24)
        ridge_zone = x_norm > 0.35

        for t in range(n_frames):
            surge = float(np.exp(-0.5 * ((t - 5.5) / 1.8) ** 2))
            early_wind = float(np.exp(-0.5 * ((t - 3.8) / 1.4) ** 2))

            rain_base = float(w_rain[t]) if w_rain and t < len(w_rain) else (
                42.0 * early_wind if ("flood" in cat or "storm" in cat) else 1.5 * (1.0 - surge)
            )
            wind_base = float(w_wind[t]) if w_wind and t < len(w_wind) else (
                6.0 + 18.0 * early_wind if ("storm" in cat or "wildfire" in cat or "flood" in cat) else 7.0
            )
            temp_base = float(w_temp[t]) if w_temp and t < len(w_temp) else (
                -10.0 * surge if "ice" in cat else (34.0 + 18.0 * surge if "wildfire" in cat or "fire" in cat else 26.0 - 3.5 * early_wind)
            )

            spatial_wave = 1.0 + 0.18 * np.sin(xx * 0.15 + t * 0.3) * np.cos(yy * 0.15)
            signals["rain"][t] = np.clip(rain_base * spatial_wave, 0.0, 75.0).astype(np.float32)
            signals["wind"][t] = np.clip(wind_base + 1.8 * y_norm + rng.normal(0, 0.25, (npix, npix)), 0.5, 45.0).astype(np.float32)
            signals["temp"][t] = np.clip(temp_base + 1.4 * x_norm + (8.0 * surge * town_zone if "fire" in cat else 0.0), -30.0, 75.0).astype(np.float32)

            if "ice" in cat:
                sar = np.where(river_band, -21.0, -10.5 - (7.5 if temp_base < 0 else 0.0) * surge)
                ndvi = np.where(river_band, 0.05, 0.62 - 0.15 * surge)
                nl = np.full((npix, npix), 0.6, dtype=np.float32)
            elif "fire" in cat:
                sar = np.where(town_zone, -6.0 - 5.0 * surge, -9.0 - 2.5 * surge)
                ndvi = np.where(town_zone, 0.45 - 0.32 * surge, 0.72 - 0.15 * surge)
                nl = np.where(town_zone, 44.0 * (1.0 - 0.78 * surge), 2.0)
            else:
                flood_zone = np.abs(y_norm - 0.25 * np.sin(x_norm * 2.6)) < (0.14 + 0.26 * surge)
                sar = np.where(flood_zone, -23.5, np.where(town_zone, -4.5, -9.5))
                if wind_base > 8.0:
                    sar[river_band] += 11.0  # Wind-ripple illusion
                ndvi = np.where(river_band, 0.04, 0.74 - 0.25 * surge)
                nl = np.where(town_zone, 38.0 * (1.0 - (0.72 * surge if t >= 4 else 0.0)), 2.2)

            signals["radar"][t] = sar.astype(np.float32)
            signals["optical"][t] = np.clip(ndvi, -0.2, 0.95).astype(np.float32)
            signals["nightlights"][t] = np.clip(nl, 0.1, 65.0).astype(np.float32)

            step_flags = np.zeros((npix, npix), dtype=np.uint16)
            if wind_base > 8.0:
                step_flags[river_band] |= FLAG_WIND_RIPPLE
            if temp_base < 0.0:
                step_flags[town_zone | ridge_zone] |= FLAG_SUBZERO_FREEZE
            if rain_base > 12.0 or ("fire" in cat and surge > 0.45):
                step_flags[town_zone] |= FLAG_CLOUD_COVER
            step_flags[ridge_zone] |= FLAG_STEEP_SLOPE
            flags[t] = step_flags

    return signals, flags, base_dates


def generate_multi_sensor_cube(
    lon: float,
    lat: float,
    fov_deg: float = 0.5,
    preset_slug: str | None = None,
    npix: int = 64,
    n_frames: int = 12,
    live_weather: dict[str, Any] | None = None,
    category_hint: str | None = None,
) -> tuple[dict[str, CompiledProduct], list[SurveyPass], GridSpec]:
    """Generate 64x64 float32 multi-sensor cubes across 12 time steps for 10 products + uint16 flags."""
    signed_lon = _wrap_signed_lon(lon)
    clamped_lat = float(max(-90.0, min(90.0, lat)))
    signals, flags, date_labels = _generate_preset_physics(
        preset_slug or "",
        npix,
        n_frames,
        live_weather=live_weather,
        category_hint=category_hint,
    )

    grid = GridSpec(
        ra0=signed_lon,
        dec0=clamped_lat,
        fov_deg=float(fov_deg),
        npix=npix,
        pixscale_arcsec=round((fov_deg * 3600.0) / npix, 2),
    )

    passes: list[SurveyPass] = []
    base_mjd = 60997.0
    for t in range(n_frames):
        mjd = base_mjd + t * 2.0
        passes.append(
            SurveyPass(
                index=t,
                mjd_start=mjd - 0.5,
                mjd_end=mjd + 0.5,
                mjd_mid=mjd,
                n_exposures=6,
                label=f"Pass {t + 1}",
            )
        )

    products: dict[str, CompiledProduct] = {}

    # 1. Six fundamental Earth signals
    for sig_name in ALL_SIGNAL_IDS:
        data_cube = signals[sig_name][:, np.newaxis, :, :]  # (12, 1, 64, 64)
        frame_ids = [f"{sig_name}_f{t}" for t in range(n_frames)]
        metas = [
            FrameMeta(
                id=f"{sig_name}_f{t}",
                kind="signal",
                pass_index=t,
                pass_label=passes[t].label,
                mjd=passes[t].mjd_mid,
                date_utc=date_labels[t],
                obs_ids=[f"NASA_{sig_name.upper()}_T{t:02d}"],
                flag_summary=summarize_uint16_flags(flags[t]),
                n_inputs=1,
                stretch_hint=compute_stretch_hint(signals[sig_name][t], symmetric=False),
                mean_flux_center=float(np.mean(signals[sig_name][t, 28:36, 28:36])),
                signal=sig_name,  # type: ignore[arg-type]
                unit=SIGNAL_UNITS[sig_name],  # type: ignore[arg-type]
            )
            for t in range(n_frames)
        ]
        products[sig_name] = CompiledProduct(
            name=sig_name,
            frame_ids=frame_ids,
            data=data_cube,
            flags=flags,
            metas=metas,
            planes_per_frame=1,
        )

    # 2. pass_coadds.sfp (SAR Radar Baseline Stack)
    radar_data = signals["radar"][:, np.newaxis, :, :]
    coadd_ids = [f"coadd_p{t}" for t in range(n_frames)]
    coadd_metas = [
        FrameMeta(
            id=f"coadd_p{t}",
            kind="coadd",
            pass_index=t,
            pass_label=passes[t].label,
            mjd=passes[t].mjd_mid,
            date_utc=date_labels[t],
            obs_ids=[f"SAR_COADD_P{t:02d}"],
            flag_summary=summarize_uint16_flags(flags[t]),
            n_inputs=1,
            stretch_hint=compute_stretch_hint(signals["radar"][t], symmetric=False),
            mean_flux_center=float(np.mean(signals["radar"][t, 28:36, 28:36])),
            signal="radar",
            unit="dB",
        )
        for t in range(n_frames)
    ]
    products["pass_coadds"] = CompiledProduct(
        name="pass_coadds",
        frame_ids=coadd_ids,
        data=radar_data,
        flags=flags,
        metas=coadd_metas,
        planes_per_frame=1,
    )

    # 3. diffs.sfp (SAR Temporal Change: Frame(t) - Frame(0))
    diff_planes = []
    diff_flags = []
    diff_ids = []
    diff_metas = []
    ref_radar = signals["radar"][0]
    for t in range(n_frames):
        diff_plane = signals["radar"][t] - ref_radar
        diff_planes.append(diff_plane)
        diff_flags.append(flags[t] | flags[0])
        fid = f"diff_p{t}_minus_p0"
        diff_ids.append(fid)
        diff_metas.append(
            FrameMeta(
                id=fid,
                kind="diff",
                pass_index=t,
                pass_label=f"{passes[t].label} − {passes[0].label}",
                mjd=passes[t].mjd_mid,
                date_utc=date_labels[t],
                obs_ids=[f"SAR_DIFF_P{t:02d}"],
                flag_summary=summarize_uint16_flags(flags[t]),
                n_inputs=2,
                stretch_hint=compute_stretch_hint(diff_plane, symmetric=True),
                ref_pass_index=0,
                signal="radar",
                unit="dB Δ",
            )
        )
    products["diffs"] = CompiledProduct(
        name="diffs",
        frame_ids=diff_ids,
        data=np.stack(diff_planes, axis=0)[:, np.newaxis, :, :],
        flags=np.stack(diff_flags, axis=0),
        metas=diff_metas,
        planes_per_frame=1,
    )

    # 4. coldglow.sfp (Thermal / Physical Energy Excursion)
    cg_planes = []
    cg_ids = []
    cg_metas = []
    for t in range(n_frames):
        # High temperature or anomalous rain energy
        cg_plane = np.clip((signals["temp"][t] - 20.0) / 20.0 + (signals["rain"][t] / 30.0), 0.0, 5.0)
        cg_planes.append(cg_plane)
        fid = f"coldglow_p{t}"
        cg_ids.append(fid)
        cg_metas.append(
            FrameMeta(
                id=fid,
                kind="coldglow",
                pass_index=t,
                pass_label=passes[t].label,
                mjd=passes[t].mjd_mid,
                date_utc=date_labels[t],
                obs_ids=[f"COLDGLOW_P{t:02d}"],
                flag_summary=summarize_uint16_flags(flags[t]),
                n_inputs=2,
                stretch_hint=compute_stretch_hint(cg_plane, symmetric=False),
                signal="temp",
                unit="thermal index",
            )
        )
    products["coldglow"] = CompiledProduct(
        name="coldglow",
        frame_ids=cg_ids,
        data=np.stack(cg_planes, axis=0)[:, np.newaxis, :, :],
        flags=flags,
        metas=cg_metas,
        planes_per_frame=1,
    )

    # 5. rgb.sfp (Rich False-Color Multi-Sensor Earth RGB: R=Temp/Urban Heat, G=NDVI/Radar Land, B=Water/Rain/Blackout)
    rgb_cubes = []
    rgb_ids = []
    rgb_metas = []
    for t in range(n_frames):
        water_prob = np.clip((-14.0 - signals["radar"][t]) / 11.0, 0.0, 1.0)
        rain_glow = np.clip(signals["rain"][t] / 45.0, 0.0, 1.0)
        heat_glow = np.clip((signals["temp"][t] - 18.0) / 30.0, 0.0, 1.0)
        nl_glow = np.clip(signals["nightlights"][t] / 45.0, 0.0, 1.0)
        r_chan = np.clip(0.55 * heat_glow + 0.55 * nl_glow, 0.05, 1.0)
        g_chan = np.clip(0.75 * signals["optical"][t] + 0.25 * nl_glow - 0.35 * water_prob, 0.04, 1.0)
        b_chan = np.clip(0.72 * water_prob + 0.45 * rain_glow + 0.15 * nl_glow, 0.08, 1.0)
        cube = np.stack([r_chan, g_chan, b_chan], axis=0)  # (3, 64, 64)
        rgb_cubes.append(cube)
        fid = f"rgb_p{t}"
        rgb_ids.append(fid)
        rgb_metas.append(
            FrameMeta(
                id=fid,
                kind="rgb",
                pass_index=t,
                pass_label=passes[t].label,
                mjd=passes[t].mjd_mid,
                date_utc=date_labels[t],
                obs_ids=[f"RGB_COMPOSITE_P{t:02d}"],
                flag_summary=summarize_uint16_flags(flags[t]),
                n_inputs=3,
                stretch_hint=StretchHint(p_lo=0.0, p_hi=1.0),
            )
        )
    products["rgb"] = CompiledProduct(
        name="rgb",
        frame_ids=rgb_ids,
        data=np.stack(rgb_cubes, axis=0),  # (12, 3, 64, 64)
        flags=flags,
        metas=rgb_metas,
        planes_per_frame=3,
    )

    return products, passes, grid


# -----------------------------------------------------------------------------
# 6-Signal Rhythm Temporal Extraction Engine
# -----------------------------------------------------------------------------

def extract_signal_rhythm_at(
    lon: float,
    lat: float,
    session_dir: Path,
    manifest: SessionManifest,
) -> SpectrumResult:
    """Extract full 12-time-step temporal rhythm across all 6 Earth signals for clicked coordinates."""
    wcs = _wcs_from_manifest(manifest)
    try:
        px_raw, py_raw = wcs.all_world2pix([[lon, lat]], 0)[0]
    except Exception:
        px_raw, py_raw = np.nan, np.nan

    npix = manifest.grid.npix if (manifest.grid and manifest.grid.npix) else 64
    max_idx = npix - 1
    if np.isnan(px_raw) or np.isnan(py_raw):
        ix, iy = (32, 32) if npix >= 64 else (npix // 2, npix // 2)
    else:
        ix = int(np.clip(round(px_raw), 0, max_idx))
        iy = int(np.clip(round(py_raw), 0, max_idx))

    series: dict[str, list[float]] = {}
    dates: list[str] = []
    points: list[SpectrumPoint] = []

    # Attempt to load signal data from pre-baked SFP1 framepacks in session_dir
    frames_dir = session_dir / "frames"
    loaded_signals: dict[str, np.ndarray] = {}
    loaded_flags: np.ndarray | None = None

    for sig in ALL_SIGNAL_IDS:
        sfp_path = frames_dir / f"{sig}.sfp"
        if sfp_path.exists():
            try:
                _, data, flg = decode_framepack(sfp_path.read_bytes())
                loaded_signals[sig] = data[:, 0]  # (12, 64, 64)
                if loaded_flags is None and flg is not None:
                    loaded_flags = flg
            except Exception:
                pass

    # If any signals missing on disk, synthesize matching cube
    if len(loaded_signals) < len(ALL_SIGNAL_IDS):
        synth_signals, synth_flags, synth_dates = _generate_preset_physics(
            manifest.target.slug or "",
            npix=manifest.grid.npix,
            n_frames=len(manifest.passes) if manifest.passes else 12,
        )
        for sig in ALL_SIGNAL_IDS:
            if sig not in loaded_signals:
                loaded_signals[sig] = synth_signals[sig]
        if loaded_flags is None:
            loaded_flags = synth_flags

    # Extract pixel timeseries
    n_steps = loaded_signals["radar"].shape[0]
    for t in range(n_steps):
        # Extract dates from manifest frames if available
        if manifest.frames and "radar" in manifest.frames and t < len(manifest.frames["radar"]):
            dates.append(manifest.frames["radar"][t].date_utc)
        else:
            dates.append(f"Day {t + 1}")

    for sig in ALL_SIGNAL_IDS:
        vals = [round(float(loaded_signals[sig][t, iy, ix]), 3) for t in range(n_steps)]
        series[sig] = vals

    # Create backward compatible SpectrumPoint objects
    for t in range(n_steps):
        points.append(
            SpectrumPoint(
                wavelength_um=float(t + 1),  # Step index as pseudo-wavelength
                flux_mjysr=series["radar"][t],
                err=0.1,
                detector=1,
                mjd=manifest.passes[t].mjd_mid if t < len(manifest.passes) else float(t),
                obs_id=f"T{t:02d}",
                flagged=bool(loaded_flags is not None and (loaded_flags[t, iy, ix] != 0)),
            )
        )

    # Synthesize physical cause-and-effect narrative story for this pixel
    r_val = series["radar"]
    p_val = series["rain"]
    w_val = series["wind"]
    t_val = series["temp"]
    o_val = series["optical"]
    n_val = series["nightlights"]

    peak_rain_idx = int(np.argmax(p_val))
    min_radar_idx = int(np.argmin(r_val))
    max_wind_idx = int(np.argmax(w_val))
    max_temp_idx = int(np.argmax(t_val))
    min_night_idx = int(np.argmin(n_val))

    signed_lon = _wrap_signed_lon(lon)
    hemi_lon = f"{abs(signed_lon):.3f}° {'E' if signed_lon >= 0 else 'W'}"
    hemi_lat = f"{abs(lat):.3f}° {'N' if lat >= 0 else 'S'}"
    story_parts = [
        f"Location ({hemi_lat}, {hemi_lon}):",
        f"Baseline radar starts at {r_val[0]:.1f} dB with vegetation greenness {o_val[0]:.2f} NDVI and night lights {n_val[0]:.1f} nW/cm²/sr.",
    ]

    if max(p_val) > 10.0:
        story_parts.append(
            f"Precipitation peaked at step {peak_rain_idx + 1} ({p_val[peak_rain_idx]:.1f} mm/hr), "
            f"triggering a radar backscatter excursion down to {r_val[min_radar_idx]:.1f} dB."
        )
    elif max(t_val) > 35.0:
        story_parts.append(
            f"Surface temperature spiked to {t_val[max_temp_idx]:.1f}°C at step {max_temp_idx + 1}, "
            f"causing acute dielectric drying and thermal vegetation stress."
        )

    if n_val[0] > 10.0 and min(n_val) < n_val[0] * 0.4:
        story_parts.append(
            f"Community nightlights dropped by {((n_val[0] - n_val[min_night_idx]) / n_val[0]) * 100.0:.0f}% "
            f"at step {min_night_idx + 1}, corroborating electrical grid failure or disaster impact."
        )

    # Check illusion flags at this pixel
    pixel_flags = int(loaded_flags[:, iy, ix].max()) if loaded_flags is not None else 0
    illusion_notes = []
    if pixel_flags & FLAG_WIND_RIPPLE:
        illusion_notes.append("Wind-Ripple Illusion (bit 1: surface chop elevated SAR backscatter)")
    if pixel_flags & FLAG_SUBZERO_FREEZE:
        illusion_notes.append("Sub-Zero Freeze Illusion (bit 2: dielectric drop lowered SAR returns)")
    if pixel_flags & FLAG_STEEP_SLOPE:
        illusion_notes.append("Steep-Slope Slip (bit 3: topographic layover/shadow)")
    if pixel_flags & FLAG_CLOUD_COVER:
        illusion_notes.append("Cloud Cover Blanking (bit 4: optical obscured while SAR penetrated)")

    if illusion_notes:
        story_parts.append("AI Illusion Guard detected: " + "; ".join(illusion_notes) + ".")
    else:
        story_parts.append("Signals show uncorrupted clear physical coupling across all sensors.")

    location_story = " ".join(story_parts)

    signed_out_lon = round(_wrap_signed_lon(lon), 6)
    clamped_out_lat = round(max(-90.0, min(90.0, lat)), 6)
    return SpectrumResult(
        ra=signed_out_lon,
        dec=clamped_out_lat,
        lon=signed_out_lon,
        lat=clamped_out_lat,
        series=series,
        dates=dates,
        units=SIGNAL_UNITS,
        location_story=location_story,
        points=points,
        aperture_arcsec=manifest.grid.pixscale_arcsec,
        n_used=len(points),
        n_rejected=0,
        note=f"Sampled at basin cell ({ix}, {iy}) across 12 multi-sensor passes.",
    )
