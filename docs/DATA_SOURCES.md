# Data Sources & Citations

**SAR Symphony** uses exclusively **open, public, zero-API-key Earth observation APIs, map tile services, and scientific archives**, paired with pre-baked curated caches (`cache/presets/`) and deterministic offline fallbacks so live demonstrations never stall if external APIs are rate-limited or unreachable.

---

## Official Space Agency, Mapping & Environmental Datasets

Exact citations returned by `DEFAULT_CITATIONS` (`backend/app/pipeline/session.py`), live API clients (`backend/app/science/earth_signals.py`, `backend/app/api/eonet.py`, `backend/app/api/ai_story.py`), NASA GIBS layer references (`backend/app/science/ai_director.py`, `backend/app/core/presets.py`), and Leaflet map tiles (`frontend/src/components/viewer/StoryMapCanvas.tsx`):

| Signal / Role | Mission / Platform | Organization / Archive | Identifier / Endpoint |
| --- | --- | --- | --- |
| **Radar Backscatter (`radar`, dB)** | NASA-ISRO SAR (**NISAR**) & Copernicus **Sentinel-1** GRD | NASA Alaska Satellite Facility (ASF) DAAC / ESA | DOI: `10.5067/SENTINEL-1/SAR_GRD` · Search API: `https://api.daac.asf.alaska.edu/services/search/param` |
| **Precipitation (`rain`, mm/hr)** | **NASA GPM IMERG** v07 | NASA Goddard Space Flight Center | DOI: `10.5067/GPM/IMERG/3B-HH/07` · `https://gpm.nasa.gov/data/imerg` · GIBS Layer: `IMERG_Precipitation_Rate` (`GoogleMapsCompatible_Level6`) |
| **Wind & Reanalysis (`wind`, m/s)** | **NASA MERRA-2** & **CYGNSS** | NASA GMAO / NASA Langley POWER | DOI: `10.5067/A7S6XP56VZWS` · `https://gmao.gsfc.nasa.gov/reanalysis/MERRA-2/` · `https://power.larc.nasa.gov/api/temporal/daily/point` |
| **Land Surface Temp (`temp`, °C)** | **NASA MODIS** / **ECOSTRESS** LST | NASA LP DAAC / JPL | GIBS Layer: `MODIS_Terra_Land_Surface_Temp_Day` |
| **Optical Vegetation (`optical`, NDVI)** | Copernicus **Sentinel-2** & **NASA VIIRS** NDVI | ESA Copernicus / NASA | `https://www.copernicus.eu/en/access-data` · GIBS Layers: `MODIS_Terra_CorrectedReflectance_TrueColor`, `VIIRS_SNPP_CorrectedReflectance_TrueColor` |
| **Nighttime Lights (`nightlights`, nW/cm²/sr)** | **NASA Black Marble VNP46A2** | NASA GSFC | DOI: `10.5067/VIIRS/VNP46A2.001` · `https://blackmarble.gsfc.nasa.gov/` · GIBS Layer: `VIIRS_SNPP_DayNightBand_At_Sensor_Radiance` (`GoogleMapsCompatible_Level8`) |
| **Active Natural Events Feed** | **NASA EONET v3** | NASA Earth Observatory | `https://eonet.gsfc.nasa.gov/api/v3/events` |
| **Place Geocoding, Forecast & Historical Meteorology** | **Open-Meteo** Geocoding, Forecast & Historical Archive APIs | Open-Meteo (Public Zero-Key API) | `https://geocoding-api.open-meteo.com/v1/search` · `https://api.open-meteo.com/v1/forecast` · `https://archive-api.open-meteo.com/v1/archive` |
| **Geospatial Basemaps & WMTS Satellite Tiles** | **Esri ArcGIS Online** & **NASA GIBS EOSDIS** | Esri / NASA EOSDIS | `https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}` · `https://server.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{z}/{y}/{x}` · `https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/` |

---

## Online vs. Offline Data Behavior

1. **5 Flagship Presets (`cache/presets/<slug>/`):** Pre-baked on disk (`10` `.sfp` framepacks, `manifest.json`, `spectrum.json`, `overlays.json`, `thumb.webp` per event) using documented NASA mission characteristics and real event meteorology (`kandy-floods`, `maui-wildfire`, `amazon-drought-fire`, `mahaweli-rice`, `jakobshavn-glacier`). Zero network latency and 100% deterministic.
2. **Historical Disaster Catalog & Live Place Queries (`GET /api/story/live`, `GET /api/explore`, `GET /api/eonet`):**
   - Matches iconic documented events (*Dubai 2024 Floods*, *Valencia DANA 2024*, *Pakistan 2022 Monsoon*, *Hurricane Helene 2024*, *Derna 2023 Floods*, *Cyclone Remal 2024*) to exact historical event dates and fetches true historical daily meteorology from **Open-Meteo Historical Archive API** (`archive-api.open-meteo.com`).
   - Queries **NASA ASF DAAC** for intersecting Sentinel-1 granule metadata (`sar_granule_id` and timestamps).
   - Queries **NASA EONET v3**, **NASA POWER Daily**, and **Open-Meteo** for live event coordinates and daily rainfall/wind/temperature series.
   - Falls back cleanly to built-in `_KNOWN_PLACES` / cached EONET fixtures and deterministic multi-signal physics synthesis when offline or throttled.
