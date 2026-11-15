"""Multi-sensor 6-signal Earth rhythm extraction."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from app.core.coords import PIXSCALE_ARCSEC
from app.models import SessionManifest, SpectrumPoint, SpectrumResult
from app.science.earth_signals import SIGNAL_UNITS, extract_signal_rhythm_at


def extract_spectrum_at(
    ra_deg: float,
    dec_deg: float,
    subimages: list[dict] | None = None,
    *,
    session_dir: Path | None = None,
    manifest: SessionManifest | None = None,
    aperture_px: float = 1.5,
    **kwargs: Any,
) -> SpectrumResult:
    """Extract the 6-signal Earth rhythm series at a geographic (lon, lat) point."""
    if session_dir is not None and manifest is not None:
        return extract_signal_rhythm_at(lon=ra_deg, lat=dec_deg, session_dir=session_dir, manifest=manifest)

    if not (math.isfinite(ra_deg) and math.isfinite(dec_deg)):
        return SpectrumResult(
            ra=0.0,
            dec=0.0,
            lon=0.0,
            lat=0.0,
            points=[],
            aperture_arcsec=round(aperture_px * PIXSCALE_ARCSEC, 1),
            n_used=0,
            n_rejected=0,
            note="Invalid non-finite coordinates.",
        )

    dates = [f"Step {t + 1}" for t in range(12)]
    series: dict[str, list[float]] = {
        "radar": [round(-12.0 + 3.0 * math.sin(t * 0.5), 4) for t in range(12)],
        "rain": [round(max(0.0, 25.0 * math.sin(t * 0.4)), 4) for t in range(12)],
        "wind": [round(5.0 + 4.0 * math.cos(t * 0.5), 4) for t in range(12)],
        "temp": [round(24.0 + 6.0 * math.sin(t * 0.3), 4) for t in range(12)],
        "optical": [round(max(0.0, min(1.0, 0.65 - 0.2 * math.sin(t * 0.4))), 4) for t in range(12)],
        "nightlights": [round(35.0 - (20.0 if 4 <= t <= 7 else 0.0), 4) for t in range(12)],
    }
    points = [
        SpectrumPoint(
            wavelength_um=float(t + 1),
            flux_mjysr=series["radar"][t],
            err=0.1,
            detector=1,
            mjd=60997.0 + t * 2.0,
            obs_id=f"T{t:02d}",
        )
        for t in range(12)
    ]
    lon_wrapped = round(((ra_deg + 180.0) % 360.0) - 180.0, 6)
    lat_clamped = round(max(-90.0, min(90.0, dec_deg)), 6)
    return SpectrumResult(
        ra=lon_wrapped,
        dec=lat_clamped,
        lon=lon_wrapped,
        lat=lat_clamped,
        series=series,
        dates=dates,
        units=dict(SIGNAL_UNITS),
        points=points,
        aperture_arcsec=round(aperture_px * PIXSCALE_ARCSEC, 1),
        n_used=12,
        n_rejected=0,
    )
