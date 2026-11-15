# SAR Symphony: Dancing with Earth's Signals

**NASA Space Apps Challenge — *Dancing with the SARs***  
**Team:** KurinjiKumaraN (Kandy, Sri Lanka)  
**License:** Apache-2.0 (`LICENSE`, `NOTICE`)  
**Pitch Deck:** [SAR_Symphony_Dancing_With_The_SARs_Pitch.pptx](pitch/SAR_Symphony_Dancing_With_The_SARs_Pitch.pptx)

---

## Overview

Synthetic Aperture Radar (SAR) sees through darkness, wildfire smoke, and dense monsoon clouds — yet single-snapshot SAR intensity maps are easily misread. Wind chop over open water mimics dry land (`+13.5 dB` backscatter), flash freezes collapse wet-snow dielectric permittivity (`-8.5 dB`), and mountain slopes trigger radar layover.

**SAR Symphony** turns multi-sensor Earth observations into an **AI-directed Domino Story-Map Studio** backed by synchronized `64×64×12` binary `SFP1` cubes and `uint16` illusion bitmasks. Instead of inspecting isolated pixels in the dark, users watch how upstream atmospheric pressure, wind jets, and heat domes trigger downstream extreme rainfall, floods, wildfires, crop cycles, glacier surges, and human power outages across space and time.

---

## Key Capabilities

### 1. Three Ways to Explore Earth Events
- **5 Flagship Benchmark Presets** (pre-baked in `cache/presets/` for zero-wait offline exploration):
  1. **Bay of Bengal Cyclone to Kandy Floods** (`kandy-floods`, Sri Lanka, Nov 2024) — Upstream `996 hPa` low & `29.4°C` SST → `18.8 m/s` wind jet → `54 mm/hr` cloudburst (`185 mm/day` under `88%` clouds) → `-24.1 dB` Mahaweli floodplains (`1,420 ha`) + `+13.5 dB` wind-ripple illusion at `14.6 m/s` on Victoria Reservoir → `-78%` Black Marble outage (`42.5` to `9.2 nW/cm²/sr`).
  2. **Pacific Gradient to Lahaina Fire & Blackout** (`maui-wildfire`, Hawaii, Aug 2023) — Hurricane Dora gradient → `35.0 m/s` katabatic downslope winds → `-85%` Black Marble grid collapse → `+58°C` thermal anomaly & `-5.2 dB` SAR building damage across `870 ha`, plus `+12 dB` harbor wave chop illusion.
  3. **Amazon Heat Dome to Drought & Fire** (`amazon-drought-fire`, Brazil, Aug 2024) — `+38.2–39.2°C` heat dome → `-4.5 dB` SAR canopy moisture drop ~21 days early while optical NDVI remains `0.68` → `+46°C` fire front through smoke → post-fire NDVI crash to `0.16` and `38 nW/cm²/sr` night glow.
  4. **Mahaweli Irrigation to Rice Heartbeat** (`mahaweli-rice`, Polonnaruwa, Sri Lanka, May–Aug 2025) — `-14.0 dB` tilled soil → `-22.5 dB` 10 cm paddy flood mirror → `+2.2 dB` vertical rice stalk double-bounce at `0.62` NDVI → `0.84` NDVI cooling canopy → `0.38` NDVI / `-13.0 dB` dry harvest.
  5. **Disko Inflow to Polar Glacier Surge** (`jakobshavn-glacier`, Greenland, Dec 2024–Jan 2025) — `0` sun hours polar night → `1.2 km²` terminus calving retreat → `-14.0°C` flash freeze collapsing wet-snow permittivity (`~80` to `3.1`) and causing a `-8.5 dB` dielectric SAR drop illusion → `42 m/day` glacier surge.
- **Live NASA EONET v3 Feed** (`GET /api/eonet`) — Click `Explore Cause` to browse real-time active disasters (wildfires, severe storms, floods, volcanoes) with automatic offline fallback.
- **Custom Place, Coordinate & Historical Event Search** (`GET /api/story/live` & `GET /api/explore`) — Search any city, `(lat, lon)` coordinate, or major disaster (including the built-in Historical Disaster Catalog: *Dubai 2024 Floods*, *Valencia DANA 2024*, *Pakistan 2022 Monsoon*, *Hurricane Helene 2024*, *Derna 2023 Floods*, *Cyclone Remal 2024*) using Open-Meteo Geocoding + Historical Archive (`archive-api.open-meteo.com`), NASA ASF DAAC Sentinel-1 search, NASA POWER Daily, and NASA EONET v3.

### 2. Six Synchronized Earth Signals (`SFP1` Framepacks)
| Signal ID | Unit | Mission / Dataset Reference |
| --- | --- | --- |
| `radar` | `dB` | NASA-ISRO NISAR & Copernicus Sentinel-1 (NASA ASF DAAC) |
| `rain` | `mm/hr` | NASA GPM IMERG |
| `wind` | `m/s` | NASA MERRA-2 / CYGNSS / Open-Meteo |
| `temp` | `°C` | NASA MODIS / ECOSTRESS Land Surface Temperature |
| `optical` | `NDVI` | Copernicus Sentinel-2 & NASA VIIRS NDVI |
| `nightlights` | `nW/cm²/sr` | NASA Black Marble VNP46A2 |

### 3. Visuals-First Domino Story-Map Studio & 4-Bit Radar Illusion Guard
- **5-Step Color-Coded Domino Director (`StoryDirectorBar.tsx`)**: Displays 5 chronological cause-and-effect Domino cards (`Orange`, `Teal`, `Blue`, `Purple`, `Rose`), a 3×2 NASA telemetry gauge grid (`Temp`, `Wind`, `Rain`, `NDVI`, `SAR Radar`, `Night Lights`), and one-click `Play Story` progression. Each scene highlights only the **2–3 relevant signals** driving that phase.
- **Interactive Geo-Causal Map (`StoryMapCanvas.tsx`)**: Powered by Leaflet over Esri World Dark Gray & World Topo basemaps, layered with NASA GIBS WMTS satellite imagery (`IMERG_Precipitation_Rate`, `VIIRS_SNPP_DayNightBand_At_Sensor_Radiance`, `MODIS_Terra_CorrectedReflectance_TrueColor`, `MODIS_Terra_Land_Surface_Temp_Day`), calibrated `64×64` SAR/signal heatmaps, interactive **Before / Peak split-curtain swipe**, animated upwind-to-impact vector arrows, and clickable map sampling.
- **Domino Flow & Causal Bridge (`PatternFinderCard.tsx`)**: Visual 5-node pipeline (`HEAT → WIND → RAIN → SAR → IMPACT`), side-by-side `Cause → Effect` vector bridge with lead-lag hours and Pearson `r` correlation bar, 2×2 Hotspot pills (`onset`, `peak_impact`, `blackout`, `illusion`), and an on-demand `Ask AI` drawer (`POST /api/ai/explain`).
- **6-Signal Timeline (`SpectrumChart.tsx`)**: Compact interactive Plotly chart with clickable frame markers and CSV export.
- **4-Bit `uint16` Radar Illusion Guard (`backend/app/core/flags.py`)**: Flags pixels affected by `FLAG_WIND_RIPPLE` (`0x0001`), `FLAG_SUBZERO_FREEZE` (`0x0002`), `FLAG_STEEP_SLOPE` (`0x0004`), and `FLAG_CLOUD_COVER` (`0x0008`).
- **60s Tour & SAR Guide (`TrainingDirectorBar.tsx`, `GlossaryModal.tsx`)**: Built-in 5-step interactive walkthrough and illustrated physical glossary.

---

## Running Locally

```powershell
# Run all 48 offline backend tests
uv run --project backend pytest -v

# Build the frontend production bundle
npm --prefix frontend run build

# Start the unified FastAPI + built SPA server on http://127.0.0.1:7860
uv run --project backend uvicorn app.main:create_app --factory --host 127.0.0.1 --port 7860 --app-dir backend
```

Or use `.\Makefile.ps1 -Task dev` to run the FastAPI backend alongside Vite hot-reload during development. Optional `GEMINI_API_KEY` enables Tier 2 generative scientific summaries on `POST /api/ai/explain`; everything works out-of-the-box with zero API keys.

---

## Documentation

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — FastAPI + React/TypeScript/Leaflet system design, API routers, `SFP1` binary format, and AI Domino Director.
- [docs/SCIENCE.md](docs/SCIENCE.md) — Multi-sensor physics, SAR backscatter mechanisms, 4-bit Radar Illusion Guard bitmasks, and resolution boundaries.
- [docs/DATA_SOURCES.md](docs/DATA_SOURCES.md) — Zero-API-key NASA, Copernicus, Open-Meteo, and Esri endpoints, DOIs, and deterministic fallback behavior.
- [docs/AI_DISCLOSURE.md](docs/AI_DISCLOSURE.md) — Disclosure of Tier 1 deterministic statistical causality, optional Tier 2 Gemini 2.5 Flash prose synthesis, and AI development tooling.

---

## Repository Layout

- `backend/` — Python (`>=3.11,<3.13`) FastAPI backend (`app/main.py`, `app/api/`, `app/core/`, `app/data/`, `app/pipeline/`, `app/science/`, `tests/`).
- `frontend/` — React 18 + TypeScript + Vite + React Context (`src/state/`) + Leaflet + Plotly UI (`src/components/`, `src/content/`, `src/engine/`, `src/styles/`).
- `cache/presets/` — Pre-baked 12-frame `SFP1` archives (`manifest.json`, `spectrum.json`, `overlays.json`, `thumb.webp`, and 10 `.sfp` framepacks per flagship event).
- `pitch/` — Updated 7-slide presentation (`SAR_Symphony_Dancing_With_The_SARs_Pitch.pptx`).
- `Dockerfile` — Unified single-container deployment serving both the FastAPI API and built frontend SPA on port `7860`.

---

## Super Intelligence (SI) Transparency & Non-Endorsement

- **Code & Data:** SI coding assistants helped build this FastAPI + React/Leaflet/Plotly workspace, prepare pre-baked `64×64×12` normalized `SFP1` cubes (`cache/presets/`), and format optional Tier 2 Gemini summaries. Disclosed via `si_disclosure` API fields, CSV headers, HTML/package metadata, and [docs/AI_DISCLOSURE.md](docs/AI_DISCLOSURE.md).
- **Images & Visualizations:** All synthesized preset thumbnails (`cache/presets/*/thumb.webp`), rendered heatmap canvases, Plotly timelines, and slide media carry discrete visible `"SI-gen"` / `"SI-generated"` watermarks.
- **Audio:** No SI-generated audio files or synthetic speech streams are used.
- **Zero NASA Branding:** Contains no NASA logos, flags, or official mission identifiers, and implies no NASA affiliation or endorsement.

