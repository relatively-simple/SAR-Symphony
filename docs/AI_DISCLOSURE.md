# Super Intelligence (SI) & AI Usage Disclosure

In accordance with NASA Space Apps Challenge submission guidelines, Team **KurinjiKumaraN** discloses how Super Intelligence (SI) tools were used across all project deliverables, media, code, and data.

---

## 1. Zero NASA Branding & Non-Endorsement Policy

- **No NASA Logos, Flags, or Mission Identifiers:** Generated code, UI layouts, synthetic preview cubes, thumbnails, charts, and presentation graphics do **not** use, contain, or modify any NASA insignia, logos (meatball/worm), flags, or official mission badges.
- References to public datasets (e.g., Sentinel-1, GPM IMERG, MERRA-2, MODIS, VIIRS Black Marble, EONET) describe underlying open Earth observation archives strictly for scientific provenance and carry no agency endorsement.

---

## 2. Disclosure by Modality (Images/Video, Audio, Code & Data)

### Images & Visualizations
- **Watermark Compliance:** All SI-assisted visual artifacts include a visible, discrete watermark (`"SI-gen"` / `"SI-generated"`):
  - **Pre-baked Preset Thumbnails (`cache/presets/*/thumb.webp`):** Generated in `backend/scripts/prewarm.py` with a discrete `"SI-gen"` corner watermark and embedded WebP EXIF `ImageDescription` metadata.
  - **Interactive Geospatial Heatmaps & Plots (`StoryMapCanvas.tsx`, `SpectrumChart.tsx`):** Synthesized `64×64` raster overlays stamp `"SI"`, the map HUD and top bar carry a discrete `"SI-gen"` corner badge, and Plotly timelines embed a bottom-right `"SI-gen"` annotation.
  - **Presentation Deck Graphics (`pitch/SAR_Symphony_Dancing_With_The_SARs_Pitch.pptx`):** All 9 embedded slide illustrations (`ppt/media/image1.png`–`image9.png`) display a subtle bottom-right `"SI-generated"` watermark alongside slide footer and OOXML core metadata notices.
- **No Video Clips:** No SI-generated video files are shipped.

### Audio
- **No Audio Generated:** SAR Symphony contains zero SI-generated speech, narration, or synthetic audio tracks. Any future audio assets will include explicit SI disclosure in descriptive text and audio metadata.

### Code & Data
- **Tier 1 — Deterministic Spatio-Temporal Causal Director (`backend/app/science/ai_director.py`, `backend/app/science/patterns.py`) [Always Active, Zero External API Key]:**
  - Uses explicit signal processing and statistical mathematics — **not generative black-box weights** — to compute lead-lag Pearson cross-correlations (`_best_lag_corr`, lags `0–3` frames converted to hours) across physical cause-effect edges (`Temperature → Wind`, `Wind → Precipitation`, `Precipitation → SAR Backscatter`, `Temperature → Optical NDVI`, `SAR Backscatter → Night Lights`).
  - Automatically classifies event categories (`infer_event_category`: `flood`, `cyclone`, `wildfire`, `glacier`, `drought`, `volcano`), selects only **2–3 relevant sensor layers per Domino Scene** (`StoryDirectorBar.tsx`), detects Hotspot markers (`onset`, `peak_impact`, `blackout`, `illusion`), and flags deceptive radar artifacts via 4-bit `uint16` QA bitmasks (`FLAG_WIND_RIPPLE`, `FLAG_SUBZERO_FREEZE`, `FLAG_STEEP_SLOPE`, `FLAG_CLOUD_COVER`).
- **Tier 2 — Optional Generative Scientific Prose (`POST /api/ai/explain` via `backend/app/api/ai_story.py`):**
  - Only when an operator sets `GEMINI_API_KEY`, `explain_event_causality` passes already-computed Tier 1 metrics and correlation values to `gemini-2.5-flash` (`generativelanguage.googleapis.com`) to format a concise summary inside the on-demand `Ask AI` drawer. Without a key, the endpoint runs strictly in deterministic `"mode": "causal_graph"` mode.
- **Metadata Disclosed Throughout Code & Data:** SI assistance in code authoring, cube synthesis (`cache/presets/`), and CSV/JSON outputs is documented in `si_disclosure` fields on API models (`backend/app/models.py`), CSV comment headers (`SpectrumChart.tsx`), `backend/pyproject.toml`, `frontend/package.json`, `frontend/index.html`, `NOTICE`, `README.md`, and `Dockerfile`.

---

## 3. SI Assistance in Software Engineering

- An SI coding assistant (Antigravity / Google DeepMind) assisted Team **KurinjiKumaraN** with:
  - Architecting and optimizing the FastAPI backend (`app/science/earth_signals.py`, `app/science/ai_director.py`, `app/science/patterns.py`, `app/api/ai_story.py`, `app/core/presets.py`) and React/TypeScript/Leaflet/Plotly frontend.
  - Authoring and synchronizing repository documentation (`README.md`, `docs/*.md`), pitch deck layouts (`pitch/SAR_Symphony_Dancing_With_The_SARs_Pitch.pptx`), and automated verification tests (`backend/tests/`).
- All scientific framing, event selection, domain physics validation, and final code review remain the work of Team **KurinjiKumaraN**.
