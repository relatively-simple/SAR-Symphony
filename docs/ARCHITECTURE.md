# SAR Symphony Architecture

## System Overview

**SAR Symphony** (`"SAR Symphony — Dancing with Earth's Signals"` in `backend/app/main.py`) runs as a unified **FastAPI + Uvicorn** backend paired with a **React 18 / TypeScript / Vite / Leaflet / Plotly** frontend (served either as a Vite dev UI or via FastAPI static SPA mounting from `cfg.spx_frontend_dist`, matching the single-container `Dockerfile` target on port `7860`).

```
+-----------------------------------------------------------------------+
| Frontend SPA (React 18, TypeScript, React Context, Leaflet, Plotly)   |
|  - TopNav + Explore Cause Drawer + TrainingDirectorBar (60s Tour)     |
|  - StoryDirectorBar (5 Color-Coded Domino Cards + 3x2 NASA Gauges)    |
|  - StoryMapCanvas (Leaflet Esri Dark/Topo + NASA GIBS WMTS +          |
|    Before/Peak Curtain Swipe + Animated Causal Vectors + SAR Heatmap) |
|  - PatternFinderCard (5-Node Domino Flow + Cause->Effect + Ask AI)    |
|  - SpectrumChart (6-Signal Plotly Timeline + CSV Export)              |
|  - GlossaryModal (SAR Science & Illusion Bitmask Guide)               |
+-----------------------------------------------------------------------+
                                   |
                        HTTP / SSE / GZip / SFP1
                                   v
+-----------------------------------------------------------------------+
| FastAPI Backend (Python >=3.11,<3.13, backend/app/main.py)            |
|  - API Routers: health, targets, eonet, explore, sessions, frames,    |
|    spectrum, overlays, ai_story                                       |
|  - Pipeline & Core: session.py, presets.py, flags.py, run.py           |
|  - Data & Clients: catalogs.py, cache.py, http.py                     |
|  - Science & AI: earth_signals.py, patterns.py, ai_director.py        |
+-----------------------------------------------------------------------+
          |                                      |
          v                                      v
+---------------------------+     +-------------------------------------+
| Disk Cache                |     | Live Zero-Key External APIs         |
|  - cache/presets/<slug>/  |     |  - NASA EONET v3 (active disasters) |
|  - runtime_cache/         |     |  - NASA ASF DAAC Search (Sentinel-1)|
|    (10 .sfp packs + JSON) |     |  - NASA POWER & Open-Meteo Archive  |
+---------------------------+     |  - NASA GIBS WMTS & Esri Basemaps   |
                                  |  - Optional: Gemini 2.5 Flash       |
                                  +-------------------------------------+
```

---

## Backend API Surface (`backend/app/main.py` & `backend/app/api/`)

| Endpoint | Router | Purpose |
| --- | --- | --- |
| `GET /api/health` | `health.py` | Service health check and live NASA EONET connectivity status. |
| `GET /api/targets` | `targets.py` | Lists all 5 Flagship Earth Presets with metadata and citations. |
| `GET /api/targets/{slug}` | `targets.py` | Loads or creates a session manifest (`5` `StoryScene`s) for a flagship preset. |
| `GET /api/targets/{slug}/thumb.webp` | `targets.py` | Serves the cached preset preview thumbnail. |
| `GET /api/eonet` | `eonet.py` | Queries NASA EONET v3 active events (with deterministic offline fallback). |
| `GET /api/explore` | `explore.py` | Server-Sent Events (SSE) pipeline scanning any custom `(lat, lon)` coordinate. |
| `GET /api/sessions/{session_id}` | `sessions.py` | Returns `SessionManifest` (`story_scenes`, `citations`, `grid`, `products`, `flags`). |
| `GET /api/sessions/{session_id}/patterns` | `sessions.py` | Returns detected Earth Hotspot patterns (`onset`, `peak_impact`, `blackout`, `illusion`). |
| `GET /api/sessions/{session_id}/frames/{prod}.sfp` | `frames.py` | Streams binary `SFP1` multi-frame spatial cubes for the requested product. |
| `GET /api/sessions/{session_id}/spectrum` | `spectrum.py` | Returns the 6-signal synchronized 12-step time series. |
| `GET /api/overlays` | `overlays.py` | Returns spatial overlay metadata and annotations (`source="preset"` or `"live"`). |
| `GET /api/story/live` | `ai_story.py` | Matches known historical disasters or geocodes live place/date queries (`Open-Meteo` Geocoding + Historical Archive + ASF Sentinel-1) and builds a 12-step causal story bundle (`5` `StoryScene`s). |
| `POST /api/ai/explain` | `ai_story.py` | Runs Tier 1 deterministic cross-correlation causality (and optional Tier 2 Gemini 2.5 Flash narrative prose if `GEMINI_API_KEY` is configured). |

---

## Spatial Framepack Model (`SFP1`)

Each session exposes **10 binary `SFP1` framepacks** (`ALL_PRODUCT_NAMES` in `backend/app/science/earth_signals.py`):
- **6 Primary Earth Signals:** `radar` (`dB`), `rain` (`mm/hr`), `wind` (`m/s`), `temp` (`°C`), `optical` (`NDVI`), `nightlights` (`nW/cm²/sr`).
- **4 Composite & Diagnostic Products:** `pass_coadds`, `diffs`, `rgb`, `coldglow`.

Each framepack stores **`12` sequential timestamps** (`n_frames=12`) over a **`64×64` float32 spatial grid** paired with **`uint16` illusion bitmasks** (`backend/app/core/flags.py`):
- `FLAG_WIND_RIPPLE = 0x0001`
- `FLAG_SUBZERO_FREEZE = 0x0002`
- `FLAG_STEEP_SLOPE = 0x0004`
- `FLAG_CLOUD_COVER = 0x0008`

---

## AI Story Director (`backend/app/science/ai_director.py`)

The backend AI Director operates in two explicit tiers:
1. **Tier 1 (Always Active, Zero External API Key):** `_best_lag_corr` evaluates lead-lag Pearson correlations (`lag` from `0` to `3` steps, converted to hours) across physical pathways (`Temperature → Wind`, `Wind → Precipitation`, `Precipitation → SAR Backscatter`, `Temperature → Optical NDVI`, `SAR Backscatter → Night Lights`). `infer_event_category` classifies events (`flood`, `cyclone`, `wildfire`, `glacier`, `drought`, `volcano`) and `build_dynamic_story_bundle` constructs 5 ordered `StoryScene` objects containing `CameraView`, `CausalLink`, `GeoFeatureOverlay`, `key_metrics`, `gibs_layer`, `gibs_date`, and `sar_granule_id`.
2. **Tier 2 (Optional `GEMINI_API_KEY`):** `explain_event_causality` invokes `gemini-2.5-flash` (`generativelanguage.googleapis.com`) to synthesize a 3–4 sentence narrative grounded in those verified correlations; without a key, it cleanly returns `"mode": "causal_graph"`.

---

## Frontend Studio Architecture (`frontend/src/`)

State is coordinated via React Context (`frontend/src/state/store.ts`) paired with binary `SFP1` decoding (`frontend/src/engine/framepack.ts`):
- **`StoryMapCanvas.tsx`**: Renders the regional geospatial studio using Leaflet (`Esri World Dark Gray Base` & `World Topo Map` base layers), live NASA GIBS WMTS tiles, canvas-rendered `64×64` calibrated SAR/signal heatmaps, interactive **Before / Peak split-curtain comparison swipe**, SVG upwind-to-impact vector arrows (`CausalLink`), and clickable hotspot markers (`pickCoordinate`).
- **`StoryDirectorBar.tsx` & `PatternFinderCard.tsx`**: Present the 5-step color-coded Domino chain (`#f97316`, `#14b8a6`, `#3b82f6`, `#a855f7`, `#f43f5e`), 3×2 NASA telemetry gauges, 5-node Domino Flow Pipeline, Cause→Effect vector bridge, 2×2 Hotspot selector pills, and an on-demand `Ask AI` drawer.
- **`SpectrumChart.tsx`**: Renders the 6-Signal Plotly timeline (`plotly.js-basic-dist-min`) with clickable timestamp scrubbing and CSV download.
