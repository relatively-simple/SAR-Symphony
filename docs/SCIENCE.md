# SAR Symphony Science & Physics Guide

## Core Scientific Idea

No catastrophic or seasonal Earth event belongs to a single sensor. Atmospheric pressure gradients drive winds; winds steer atmospheric moisture into extreme rain; surface water, burning vegetation, or freezing snowpack alter synthetic aperture radar (SAR) microwave backscatter; and infrastructure failures register immediately as drops in nighttime radiance.

**SAR Symphony** couples **6 complementary Earth signals** across **12 synchronized time steps** so cause, surface effect, illusion artifact, and human impact can be read side by side.

| Signal ID | Unit | Observable Physical Quantity |
| --- | --- | --- |
| `radar` | `dB` | C-/L-band SAR calibrated backscatter ($\sigma^0$) |
| `rain` | `mm/hr` | Precipitation rate (NASA GPM IMERG / atmospheric model) |
| `wind` | `m/s` | Near-surface wind speed (NASA MERRA-2 / CYGNSS / Open-Meteo) |
| `temp` | `°C` | Land surface / boundary thermal state (MODIS / ECOSTRESS LST) |
| `optical` | `NDVI` | Normalized Difference Vegetation Index (Sentinel-2 / VIIRS) |
| `nightlights` | `nW/cm²/sr` | Nighttime visible radiance (NASA Black Marble VNP46A2) |

---

## How SAR Sees What Optical Misses (Physical Signatures Modeled)

Across the 5 Flagship Presets (`backend/app/core/presets.py`), the system demonstrates five distinct SAR & multi-sensor regimes:

1. **Flood Specular Reflection (`kandy-floods`, Sri Lanka):**
   - Smooth standing floodwater acts like a radar mirror, reflecting C-/L-band pulses away from the sensor and dropping SAR backscatter sharply (`-24.1 dB` across `1,420 ha` of Mahaweli floodplains), even beneath `88%` dense monsoon cloud cover that blocks optical satellites.
   - Upstream triggers: `996 hPa` Bay of Bengal low over `29.4°C` SST drives `18.8 m/s` wind jets and `54 mm/hr` (`185 mm/day`) rainfall, followed by a `-78%` NASA Black Marble grid outage (`42.5` → `9.2 nW/cm²/sr`).
2. **Cyclone Winds, Urban Fire Damage & Blackout (`maui-wildfire`, Hawaii):**
   - Hurricane Dora's pressure gradient drives `35.0 m/s` katabatic downslope winds, collapsing the power grid (`-85%` Black Marble), igniting `+58°C` thermal fire fronts, and dropping urban SAR backscatter (`-5.2 dB` over `870 ha`) as upright walls with strong double-bounce corner reflections collapse into rubble.
3. **Sub-Canopy Moisture Early Warning (`amazon-drought-fire`, Brazil):**
   - Intense heat domes (`+38.2–39.2°C`) dry woody stems and sub-canopy moisture ~21 days before chlorophyll collapses: SAR detects a `-4.5 dB` dielectric drop while optical NDVI still reads healthy green (`0.68`). When fire breaks out (`+46°C` thermal signal through smoke), NDVI collapses to `0.16` and fire glow peaks at `38 nW/cm²/sr`.
4. **Crop Phenology Double-Bounce Heartbeat (`mahaweli-rice`, Polonnaruwa):**
   - SAR directly tracks rice cultivation phases through monsoon clouds: `-14.0 dB` tilled soil → `-22.5 dB` `10 cm` flooded paddy mirror → `+2.2 dB` vertical rice stalk **double-bounce** resonance (`0.62` NDVI) → `0.84` NDVI peak cooling canopy → `0.38` NDVI / `-13.0 dB` dry harvest.
5. **Polar Night & Dielectric Permittivity Collapse (`jakobshavn-glacier`, Greenland):**
   - With `0` sun hours in polar darkness, optical imagery is blind while SAR tracks a `1.2 km²` calving retreat and `42 m/day` ice flow surge.

---

## The 4-Bit `uint16` Radar Illusion Guard (`backend/app/core/flags.py`)

Raw SAR intensity drops or spikes can be **physically real illusions** rather than flood extension or dry ground. Every `64×64` pixel carries a compact `uint16` QA bitmask so users can toggle **Illusion Guard ON/OFF** and avoid misinterpretation:

| Bitmask Constant | Value | Physical Illusion Mechanism | Concrete Flagship Example |
| --- | --- | --- | --- |
| `FLAG_WIND_RIPPLE` | `0x0001` | Strong surface wind creates Bragg capillary waves on open water, raising SAR backscatter so flooded reservoirs look like dry rough land. | `+13.5 dB` wind-ripple boost at `14.6 m/s` on Victoria Reservoir (`kandy-floods`); `+12 dB` harbor chop (`maui-wildfire`). |
| `FLAG_SUBZERO_FREEZE` | `0x0002` | Freezing collapses liquid water dielectric permittivity ($\varepsilon_r$ from `~80` to `~3.1` in ice), plunging SAR backscatter without water disappearing. | `-8.5 dB` dielectric freeze drop during `-14.0°C` flash freeze (`jakobshavn-glacier`). |
| `FLAG_STEEP_SLOPE` | `0x0004` | Steep mountain relief causes foreshortening, radar layover, and shadow slip unrelated to flooding. | Knuckles / hill-country slopes in `kandy-floods`; West Maui slopes in `maui-wildfire`. |
| `FLAG_CLOUD_COVER` | `0x0008` | Heavy clouds or thick smoke block visible/NIR sensors, leaving optical NDVI stale or dark while SAR penetrates unimpeded. | `88%` monsoon cloud cover during Kandy cloudburst (`kandy-floods`); dense smoke over Amazon fires (`amazon-drought-fire`). |

---

## Lead-Lag Causal Correlation & Resolution Boundaries

- **Deterministic Causal Graph (`_best_lag_corr` in `backend/app/science/ai_director.py`):** Evaluates Pearson cross-correlations across lags `0..3` time steps (converted to hours) along domain-grounded causal edges:
  `(temp → wind)`, `(wind → rain)`, `(rain → radar)`, `(temp → optical)`, and `(radar → nightlights)`.
- **Spatial & Temporal Normalization (`64×64 × 12`):** Both curated presets (`cache/presets/`) and live EONET/coordinate scans normalize heterogeneous multi-sensor signatures onto aligned `64×64` float32 `SFP1` grids across `12` frames so frame-by-frame playback, map sampling, interactive Before/Peak split-curtain map swipe, multi-layer causal vector overlays, and Hotspot detection operate at sub-second speed even offline.
- **Honest Calibration Caveat:** Curated flagship presets synthesize peer-reviewed event magnitudes and NASA data characteristics into compact `64×64` grids rather than shipping gigabyte GeoTIFF/GRD rasters in-repo; live scans couple real NASA ASF Sentinel-1 granule metadata, NASA EONET event locations, and Open-Meteo/NASA POWER meteorology with physics-consistent multi-signal grids.
