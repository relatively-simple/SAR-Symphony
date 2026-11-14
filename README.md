---
title: SPHEREx Discovery Flipbook (KurinjiKumaraN)
emoji: 🔭
colorFrom: blue
colorTo: pink
sdk: docker
app_port: 7860
pinned: false
license: apache-2.0
---

# SPHEREx Discovery Flipbook — Team KurinjiKumaraN

Interactive epoch-aligned astronomical flipbook and 0.75–5.0 µm spectroscopic explorer built for **NASA Space Apps 2026 Challenge 12: *Planet X and SPHEREx*** (Kandy, Sri Lanka).

Instead of flattening SPHEREx exposures into static blurry stacks that wash out moving worlds, this workbench automatically groups NASA/IPAC IRSA **DR1 + QR3 Level-2** data by **6-month survey pass**, removes per-exposure zodiacal foreground (`ZODI`), masks fatal quality bits (`FLAGS`), reprojects every exposure onto a common **North-Up ICRS** sky grid (`6.15"/px`), and streams compact binary Float32 stacks (`SFP1`) for instant interactive discovery.

## Features
- **Guided Discovery Missions (Instant Offline Presets):**
  1. **Barnard's Star** — Textbook `10.4"/yr` fast mover leaving a razor-sharp red/cyan dipole between 2025–2026 passes.
  2. **epsilon Indi B** — Nearby bright-star companion testbed (~`6.7'` ESE of `eps Ind`, `4.7"/yr` motion).
  3. **WISE 0855-0714** — Coldest known Y-dwarf brown dwarf (`~250 K`) sampled across **Cold Glow (`D5+D6: 3.8–5.0 µm`)** while moving `8.1"/yr` West of its 2010 WISE discovery circle.
  4. **RW Aurigae** — Accreting T Tauri young binary fluctuating in infrared brightness across SPHEREx passes.
  5. **R Draconis** — Large-amplitude Mira variable star pulsing smoothly over 6-month intervals.
- **Free Sky Explorer (`?ra=&dec=&fov=&lens=`):** Point at *any* sky coordinate (`0.05°`, `0.10°`, or `0.25°`), fetch only minimal 2D cutouts via HTTP `Range` requests against full IRSA MEFs (skipping multi-megabyte `EPSF` tables and decoding row-compressed Rice `FLAGS` tiles cleanly), and watch live 5-stage SSE progress.
- **Click-to-Spectrum (`WCS-WAVE`):** Click any pixel on the sky canvas to extract background-subtracted calibrated brightness (`MJy/sr`) across all six SPHEREx LVF detectors (`D1–D6`, `0.75–5.0 µm`).
- **Cross-Mission Anchors:** Proper-motion-propagated **Gaia DR3** crosses (IRSA Gator & ESA TAP), **AllWISE** (`2010–2011`) circles (IRSA Gator), and an **Aladin Lite v3** wide-sky modal.

## Quick Local Start

```powershell
# 1. Backend tests (offline suite)
.\Makefile.ps1 test

# 2. Build React UI into frontend/dist
.\Makefile.ps1 build

# 3. Serve unified app on http://127.0.0.1:7860
.\Makefile.ps1 serve
```

See [docs/SCIENCE.md](docs/SCIENCE.md), [docs/DATA_SOURCES.md](docs/DATA_SOURCES.md), [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md), and [docs/AI_DISCLOSURE.md](docs/AI_DISCLOSURE.md) for methodology, archive citations, and AI transparency.

## License
Apache License 2.0 — see [LICENSE](LICENSE) and [NOTICE](NOTICE).
