# System Architecture

Unified single-service Python + React architecture designed for free zero-key deployment (`port 7860`, Docker / Hugging Face Spaces CPU Basic).

```
Browser (React + TypeScript + HTML5 Canvas + Plotly.js + Aladin Lite v3)
   |
   +-- GET /api/targets .......................... 5 NASA presets + readiness
   +-- GET /api/targets/{slug} ................... Pre-baked SessionManifest (0-wait offline)
   +-- GET /api/targets/{slug}/thumb.webp ........ 160x160 North-Up preview thumbnail
   +-- GET /api/explore?ra=&dec=&fov= ............ Live 5-stage SSE pipeline vs IRSA SIAv2
   +-- GET /api/sessions/{id}/frames/{prod}.sfp .. Binary SFP1 float32 cube + uint16 flags
   +-- GET /api/sessions/{id}/spectrum?ra=&dec= .. On-the-fly WCS-WAVE 0.75-5.0 um spectrum
   +-- GET /api/overlays?ra=&dec=&fov=&mjd= ...... Gaia DR3 (ESA TAP) + AllWISE (Gator)
   +-- GET /api/health ........................... Archive & preset readiness probe
   v
FastAPI Server (uvicorn app.main:create_app --factory)
   +-- Preset Cache: cache/presets/<slug>/ (manifest, frames/*.sfp, overlays, spectrum, raw_subimages)
   +-- Runtime LRU Cache: runtime_cache/ (bounded .npz raw slices & session artifacts)
```

## Binary `SFP1` Framepack Wire Format
- Bytes `0..3`: ASCII magic `SFP1`
- Bytes `4..7`: `uint32` little-endian JSON header byte length `L`
- Bytes `8..8+L-1`: UTF-8 JSON `{ "npix", "n_frames", "planes_per_frame", "has_flags", "frame_ids" }`
- `0..3` null padding bytes to next 4-byte boundary (`TypedArray` alignment)
- `float32` pixel payload `[n_frames, planes_per_frame, npix, npix]` (North-Up, East-Left; `NaN` for masked gaps)
- Optional `uint16` compact 6-bit flag payload `[n_frames, npix, npix]`
