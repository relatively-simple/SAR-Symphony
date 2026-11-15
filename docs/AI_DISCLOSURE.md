# AI Usage Disclosure

In accordance with NASA Space Apps Challenge submission requirements, Team **KurinjiKumaraN** discloses both (1) how AI operates inside **SAR Symphony**, and (2) how AI tools assisted in software development.

---

## 1. AI Inside the Application (Two-Tier Causal Engine)

- **Tier 1 — Deterministic Spatio-Temporal Causal Director (`backend/app/science/ai_director.py`, `backend/app/science/patterns.py`) [Always Active, Zero External API Key]:**
  - Uses explicit signal processing and statistical mathematics — **not generative black-box weights** — to compute lead-lag Pearson cross-correlations (`_best_lag_corr`, lags `0–3` frames converted to hours) across physical cause-effect edges (`Temperature → Wind`, `Wind → Precipitation`, `Precipitation → SAR Backscatter`, `Temperature → Optical NDVI`, `SAR Backscatter → Night Lights`).
  - Automatically classifies event categories (`infer_event_category`: `flood`, `cyclone`, `wildfire`, `glacier`, `drought`, `volcano`), selects only **2–3 relevant sensor layers per Domino Scene** (`StoryDirectorBar.tsx`), detects Hotspot markers (`onset`, `peak_impact`, `blackout`, `illusion`), and flags deceptive radar artifacts via 4-bit `uint16` QA bitmasks (`FLAG_WIND_RIPPLE`, `FLAG_SUBZERO_FREEZE`, `FLAG_STEEP_SLOPE`, `FLAG_CLOUD_COVER`).
- **Tier 2 — Optional Generative Scientific Prose (`POST /api/ai/explain` via `backend/app/api/ai_story.py`):**
  - Only when an operator sets `GEMINI_API_KEY`, `explain_event_causality` passes the already-computed Tier 1 metrics and lead-lag correlation values to `gemini-2.5-flash` (`generativelanguage.googleapis.com`) to format a concise 3–4 sentence narrative summary inside the on-demand `Ask AI` drawer. Without a key, the endpoint runs strictly in deterministic `"mode": "causal_graph"` mode.
- **No Fabricated Raw Imagery:** No generative image/diffusion model is used to invent or alter satellite imagery inside the viewer.

---

## 2. AI Assistance in Development & Documentation

- An AI coding assistant (Antigravity / Google DeepMind) was used as a pair-programming tool by Team **KurinjiKumaraN** to:
  - Architect and refactor the FastAPI backend (`app/science/earth_signals.py`, `app/science/ai_director.py`, `app/science/patterns.py`, `app/api/ai_story.py`, `app/core/presets.py`) and React/TypeScript/Leaflet/Plotly frontend.
  - Draft and synchronize project documentation (`README.md`, `docs/*.md`) and pitch deck layouts (`pitch/SAR_Symphony_Dancing_With_The_SARs_Pitch.pptx`).
  - Verify data schemas, citation DOIs, and edge-case fallback behavior against actual repository files.
- All project design decisions, scientific framing (starting from local Sri Lankan Kandy floods and Polonnaruwa Mahaweli rice cycles), domain physics verification, and final code edits were reviewed and directed by Team **KurinjiKumaraN**.
