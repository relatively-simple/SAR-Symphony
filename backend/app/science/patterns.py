"""Automated spatial, temporal, and thermal pattern detection on SPHEREx cubes."""

from __future__ import annotations

import json
import math
from pathlib import Path
import warnings

from astropy.wcs import WCS
import numpy as np

from app.io.framepack import decode_framepack
from app.models import (
    OverlaySet,
    PatternCandidate,
    PatternReport,
    SessionManifest,
)


def _wcs_from_manifest(manifest: SessionManifest) -> WCS:
    """Reconstruct North-Up TAN WCS matching SessionManifest.grid."""
    g = manifest.grid
    cdelt_deg = g.pixscale_arcsec / 3600.0
    w = WCS(naxis=2)
    w.wcs.ctype = list(g.ctype)
    w.wcs.crval = [g.ra0, g.dec0]
    w.wcs.crpix = [(g.npix + 1) / 2.0, (g.npix + 1) / 2.0]
    w.wcs.cdelt = [-cdelt_deg, cdelt_deg]
    return w


def _pix_to_sky(wcs: WCS, fx: float, fy: float) -> tuple[float, float]:
    ra, dec = wcs.all_pix2world([[fx, fy]], 0)[0]
    return float(ra % 360.0), float(max(-90.0, min(90.0, dec)))


def _angsep_arcsec(ra1: float, dec1: float, ra2: float, dec2: float) -> float:
    cosd = max(math.cos(math.radians(0.5 * (dec1 + dec2))), 0.05)
    dra = ((ra2 - ra1 + 180.0) % 360.0 - 180.0) * cosd
    ddec = dec2 - dec1
    return math.hypot(dra, ddec) * 3600.0


def _compass_dir(dx_px: float, dy_px: float) -> str:
    """Return cardinal/intercardinal direction for (North=+y, East=-x) grid."""
    east = -dx_px
    north = dy_px
    ang = (math.degrees(math.atan2(east, north)) + 360.0) % 360.0
    dirs = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
    return dirs[int((ang + 22.5) // 45.0) % 8]


def _robust_z(arr: np.ndarray) -> np.ndarray:
    """Subtract spatial median and divide by robust 1.4826*MAD sigma."""
    valid = arr[np.isfinite(arr)]
    if valid.size < 9:
        return np.zeros_like(arr, dtype=np.float32)
    med = float(np.median(valid))
    mad = float(np.median(np.abs(valid - med)))
    sig = max(1.4826 * mad, 1e-5)
    return ((arr - med) / sig).astype(np.float32)


def _find_local_extrema(
    zmap: np.ndarray, *, sign: int = 1, threshold: float = 4.2, radius: int = 2
) -> list[tuple[float, int, int]]:
    """Return sorted local maxima of `sign * zmap` strictly above `threshold`."""
    h, w = zmap.shape
    signed = sign * zmap
    peaks: list[tuple[float, int, int]] = []
    for y in range(1, h - 1):
        for x in range(1, w - 1):
            v = float(signed[y, x])
            if not math.isfinite(v) or v < threshold:
                continue
            y0, y1 = max(0, y - radius), min(h, y + radius + 1)
            x0, x1 = max(0, x - radius), min(w, x + radius + 1)
            patch = signed[y0:y1, x0:x1]
            if not np.any(np.isfinite(patch)):
                continue
            if v >= float(np.nanmax(patch)) - 1e-6:
                peaks.append((v, y, x))
    peaks.sort(key=lambda item: item[0], reverse=True)
    return peaks


def _is_local_peak_at(arr: np.ndarray, y: int, x: int, radius: int = 1) -> bool:
    h, w = arr.shape
    v = float(arr[y, x])
    if not math.isfinite(v):
        return False
    patch = arr[max(0, y - radius) : min(h, y + radius + 1), max(0, x - radius) : min(w, x + radius + 1)]
    finite = patch[np.isfinite(patch)]
    return bool(finite.size > 0 and v >= float(np.max(finite)) - 1e-6)


def _has_nan_hole_nearby(arr: np.ndarray | None, y: int, x: int, radius: int = 2) -> int:
    """Count non-finite pixels inside a box around (y, x) (detects saturated [OVERFLOW] cores)."""
    if arr is None:
        return 0
    h, w = arr.shape
    patch = arr[max(0, y - radius) : min(h, y + radius + 1), max(0, x - radius) : min(w, x + radius + 1)]
    return int(np.count_nonzero(~np.isfinite(patch)))


def _aperture_sum(arr: np.ndarray, y: int, x: int, r: int = 1) -> float | None:
    h, w = arr.shape
    patch = arr[max(0, y - r) : min(h, y + r + 1), max(0, x - r) : min(w, x + r + 1)]
    valid = patch[np.isfinite(patch)]
    if valid.size < 4:
        return None
    med = float(np.nanmedian(arr)) if np.any(np.isfinite(arr)) else 0.0
    return float(np.sum(valid - med))


def _load_sfp(session_dir: Path, filename: str) -> np.ndarray | None:
    path = session_dir / "frames" / filename
    if not path.exists():
        return None
    _, data, _ = decode_framepack(path.read_bytes())
    return data


def _stack_median_z(planes: list[np.ndarray]) -> np.ndarray | None:
    if not planes:
        return None
    z_list = [_robust_z(p) for p in planes]
    stack = np.stack(z_list, axis=0)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        if len(z_list) >= 3:
            return np.nanmedian(stack, axis=0).astype(np.float32)
        return np.nanmean(stack, axis=0).astype(np.float32)


def detect_patterns(session_dir: Path, manifest: SessionManifest) -> PatternReport:
    """Detect movers, brightness variables, cold IR sources, and archive drift cleanly."""
    wcs = _wcs_from_manifest(manifest)
    pixscale = manifest.grid.pixscale_arcsec
    npix = manifest.grid.npix
    cy_center, cx_center = npix // 2, npix // 2

    coadd_data = _load_sfp(session_dir, "pass_coadds.sfp")
    diff_data = _load_sfp(session_dir, "diffs.sfp")
    cg_data = _load_sfp(session_dir, "coldglow.sfp")

    overlays: OverlaySet | None = None
    ov_path = session_dir / "overlays.json"
    if ov_path.exists():
        try:
            overlays = OverlaySet.model_validate(json.loads(ov_path.read_text(encoding="utf-8")))
        except Exception:
            overlays = None

    coadd_metas = manifest.frames.get("pass_coadds", [])
    diff_metas = manifest.frames.get("diffs", [])
    passes = manifest.passes
    past_label = passes[0].label if passes else None
    present_label = passes[-1].label if len(passes) >= 2 else past_label

    cg_mean: np.ndarray | None = None
    cg_stack_z: np.ndarray | None = None
    if cg_data is not None and cg_data.shape[0] > 0:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            cg_mean = np.nanmean(cg_data[:, 0], axis=0)
        cg_stack_z = _robust_z(cg_mean)

    short_planes = (
        [coadd_data[i, 0] for i, fm in enumerate(coadd_metas) if fm.detector in (1, 2)]
        if coadd_data is not None
        else []
    )
    short_stack_z = _stack_median_z(short_planes) if short_planes else None

    candidates: list[PatternCandidate] = []
    used_spots: list[tuple[int, int, str]] = []

    def _near_existing(y: int, x: int, kind: str, min_dist: float = 3.0) -> bool:
        return any(k == kind and math.hypot(y - py, x - px) < min_dist for py, px, k in used_spots)

    # ------------------------------------------------------------------
    # 1. Stationary / Target Variable Check First (helps separate pulsating halo diffraction!)
    # ------------------------------------------------------------------
    center_pulsation_pct = 0.0
    det_changes: list[tuple[float, int]] = []
    if coadd_metas and len(passes) >= 2:
        pass_indices = sorted({fm.pass_index for fm in coadd_metas})
        first_p, last_p = pass_indices[0], pass_indices[-1]
        for det in (3, 4, 2, 5, 1, 6):
            idx_a = [i for i, fm in enumerate(coadd_metas) if fm.pass_index == first_p and fm.detector == det]
            idx_b = [i for i, fm in enumerate(coadd_metas) if fm.pass_index == last_p and fm.detector == det]
            if not idx_a or not idx_b:
                continue
            fa = coadd_metas[idx_a[0]].mean_flux_center
            fb = coadd_metas[idx_b[0]].mean_flux_center
            if fa is not None and fb is not None and max(abs(fa), abs(fb)) > 0.35:
                base = max(min(abs(fa), abs(fb)), 0.05)
                pct = ((fb - fa) / base) * 100.0
                if abs(pct) >= 25.0:
                    det_changes.append((pct, det))
                    center_pulsation_pct = max(center_pulsation_pct, abs(pct))

    # ------------------------------------------------------------------
    # 2. Moving Object (Dipole) Detector on Multi-Band (Present - Past)
    # ------------------------------------------------------------------
    if diff_data is not None and diff_metas:
        max_p = max(fm.pass_index for fm in diff_metas)
        baseline_planes = [diff_data[i, 0] for i, fm in enumerate(diff_metas) if fm.pass_index == max_p]
        diff_z = _stack_median_z(baseline_planes)
        if diff_z is not None:
            pos_peaks = _find_local_extrema(diff_z, sign=1, threshold=4.5, radius=2)
            neg_peaks = _find_local_extrema(diff_z, sign=-1, threshold=4.5, radius=2)
            for pv, py, px in pos_peaks[:8]:
                best_neg: tuple[float, int, int, float] | None = None
                for nv, ny, nx in neg_peaks:
                    sep = math.hypot(px - nx, py - ny)
                    if 1.0 <= sep <= 6.2:
                        sym = min(pv, nv) / max(pv, nv)
                        if sym >= 0.20:
                            # Reject outer PSF diffraction ringing hugging a large saturated Mira core (>=12 NaNs in 9x9 halo)
                            mid_y, mid_x = int(round(0.5 * (py + ny))), int(round(0.5 * (px + nx)))
                            if (
                                _has_nan_hole_nearby(diff_z, mid_y, mid_x, radius=2) >= 14
                                or _has_nan_hole_nearby(cg_mean, py, px, radius=4) >= 12
                            ):
                                continue
                            score = min(pv, nv) / max(sep, 1.0)
                            if best_neg is None or score > best_neg[3]:
                                best_neg = (nv, ny, nx, score)
                if best_neg is None or _near_existing(py, px, "mover", 3.5):
                    continue
                nv, ny, nx, _ = best_neg
                sep_px = math.hypot(px - nx, py - ny)
                shift_arcsec = sep_px * pixscale
                direction = _compass_dir(px - nx, py - ny)
                ra, dec = _pix_to_sky(wcs, float(px), float(py))
                pair_snr = round(float(min(pv, nv)), 1)
                candidates.append(
                    PatternCandidate(
                        id=f"mover_{py}_{px}",
                        kind="mover",
                        title=f"Moving Object Pair (~{shift_arcsec:.1f}\" {direction})",
                        summary=(
                            f"Bright '+now' glow sits {shift_arcsec:.1f}\" {direction} of a matching "
                            f"'-before' shadow between {past_label or 'Past'} and {present_label or 'Present'} — "
                            "classical sign of a moving nearby star or brown dwarf."
                        ),
                        confidence="High" if pair_snr >= 8.0 else "Medium",
                        snr=pair_snr,
                        ra=ra,
                        dec=dec,
                        fits_x=float(px),
                        fits_y=float(py),
                        past_fits_x=float(nx),
                        past_fits_y=float(ny),
                        suggested_label="Moving World",
                        metrics={
                            "pos_snr": round(float(pv), 1),
                            "neg_snr": round(float(nv), 1),
                            "shift_arcsec": round(shift_arcsec, 1),
                            "direction": direction,
                        },
                    )
                )
                used_spots.append((py, px, "mover"))
                if len(candidates) >= 2:
                    break

    # ------------------------------------------------------------------
    # 3. Stationary Variable Detector (Monopole brightness change across passes)
    # ------------------------------------------------------------------
    if coadd_data is not None and coadd_metas and len(passes) >= 2:
        all_coadd_z = _stack_median_z([coadd_data[i, 0] for i in range(len(coadd_metas))])
        found_var = False
        if all_coadd_z is not None:
            bright_peaks = _find_local_extrema(all_coadd_z, sign=1, threshold=6.5, radius=3)
            for bv, by, bx in bright_peaks[:5]:
                if _near_existing(by, bx, "mover", 3.2) or _has_nan_hole_nearby(cg_mean, by, bx, radius=1) >= 2:
                    continue
                by_pass_flux: dict[int, list[float]] = {}
                for i, fm in enumerate(coadd_metas):
                    ap = _aperture_sum(coadd_data[i, 0], by, bx, r=1)
                    if ap is not None and abs(ap) > 0.25:
                        by_pass_flux.setdefault(fm.pass_index, []).append(ap)
                if len(by_pass_flux) >= 2:
                    p_first_med = float(np.median(by_pass_flux[min(by_pass_flux)]))
                    p_last_med = float(np.median(by_pass_flux[max(by_pass_flux)]))
                    if max(abs(p_first_med), abs(p_last_med)) < 0.6:
                        continue
                    denom = max(min(abs(p_first_med), abs(p_last_med)), 0.1)
                    pct_ap = ((p_last_med - p_first_med) / denom) * 100.0
                    if abs(pct_ap) >= 35.0:
                        verb = "brightened" if pct_ap > 0 else "dimmed"
                        ra, dec = _pix_to_sky(wcs, float(bx), float(by))
                        candidates.append(
                            PatternCandidate(
                                id=f"variable_{by}_{bx}",
                                kind="variable",
                                title=f"In-Place Brightness Swing ({pct_ap:+.0f}%)",
                                summary=(
                                    f"This object stayed fixed in space while it {verb} by "
                                    f"{abs(pct_ap):.0f}% between {past_label or 'Pass 1'} and {present_label or 'Latest Pass'}."
                                ),
                                confidence="High" if abs(pct_ap) >= 45.0 else "Medium",
                                snr=round(float(bv), 1),
                                ra=ra,
                                dec=dec,
                                fits_x=float(bx),
                                fits_y=float(by),
                                suggested_label="Flickering Star",
                                metrics={"change_pct": round(float(pct_ap), 1)},
                            )
                        )
                        used_spots.append((by, bx, "variable"))
                        found_var = True
                        break

        if not found_var and det_changes and not _near_existing(cy_center, cx_center, "mover", 3.5):
            det_changes.sort(key=lambda t: abs(t[0]), reverse=True)
            pct, det_best = det_changes[0]
            verb = "brightened" if pct > 0 else "dimmed"
            ra, dec = _pix_to_sky(wcs, float(cx_center), float(cy_center))
            candidates.append(
                PatternCandidate(
                    id=f"variable_center_d{det_best}",
                    kind="variable",
                    title=f"Target Pulsation / Eclipse ({pct:+.0f}% in D{det_best})",
                    summary=(
                        f"Center target stayed fixed in coordinates while Detector D{det_best} "
                        f"infrared brightness {verb} by {abs(pct):.0f}% across survey passes."
                    ),
                    confidence="High",
                    snr=round(min(abs(pct) / 4.0, 99.0), 1),
                    ra=ra,
                    dec=dec,
                    fits_x=float(cx_center),
                    fits_y=float(cy_center),
                    suggested_label="Flickering Star",
                    metrics={"change_pct": round(float(pct), 1), "detector": f"D{det_best}"},
                )
            )
            used_spots.append((cy_center, cx_center, "variable"))

    # ------------------------------------------------------------------
    # 4. Cold Infrared Excess / Optical-Dropout Detector (3.8-5.0 vs 0.75-1.6 um)
    # ------------------------------------------------------------------
    if cg_stack_z is not None:
        cg_peaks = _find_local_extrema(cg_stack_z, sign=1, threshold=4.5, radius=2)
        for cgv, cy, cx in cg_peaks[:6]:
            if _near_existing(cy, cx, "cold_ir", 3.0) or _has_nan_hole_nearby(cg_mean, cy, cx, radius=2) >= 2:
                continue
            # Ignore PSF ring peaks hugging a heavily saturated bright core (e.g. bright Mira/T Tauri wing)
            if _has_nan_hole_nearby(short_stack_z, cy, cx, radius=2) >= 1 or (
                _near_existing(cy, cx, "variable", 2.0) and cgv > 1500
            ):
                continue
            # Check if a bright short-NIR peak (>50% of coldglow SNR) already dominates inside 1px
            sv = float(short_stack_z[cy, cx]) if short_stack_z is not None and math.isfinite(short_stack_z[cy, cx]) else 0.0
            is_short_peak = (
                short_stack_z is not None
                and _is_local_peak_at(short_stack_z, cy, cx, radius=1)
                and sv > cgv * 1.15
            )
            cold_ratio = cgv / max(sv, 1.0)
            if cold_ratio >= 0.85 and not is_short_peak:
                ra, dec = _pix_to_sky(wcs, float(cx), float(cy))
                gaia_dist = None
                if overlays and overlays.gaia:
                    gaia_dist = min(_angsep_arcsec(ra, dec, g.ra_at_mjd, g.dec_at_mjd) for g in overlays.gaia)
                no_gaia = gaia_dist is None or gaia_dist > 5.0
                # If a variable bright star sits right at center with an optical match, skip shoulder cold_ir
                if not no_gaia and _near_existing(cy, cx, "variable", 2.0):
                    continue
                why = (
                    "Glowing distinctly in 3.8–5.0 um thermal heat with no matching Gaia visible-light star right on it"
                    if no_gaia
                    else "Glowing much stronger in cold thermal infrared (3.8–5.0 um) than in shorter starlight bands"
                )
                candidates.append(
                    PatternCandidate(
                        id=f"cold_{cy}_{cx}",
                        kind="cold_ir",
                        title=f"Cold Infrared Heat Peak ({cgv:.1f}σ at 4.5 µm)",
                        summary=f"{why} — classic signature of a cool ~250–900 K brown dwarf or dusty world.",
                        confidence="High" if (cold_ratio >= 1.5 or no_gaia) and cgv >= 6.0 else "Medium",
                        snr=round(float(cgv), 1),
                        ra=ra,
                        dec=dec,
                        fits_x=float(cx),
                        fits_y=float(cy),
                        suggested_label="Cold Heat World",
                        metrics={
                            "cold_snr": round(float(cgv), 1),
                            "short_snr": round(float(sv), 1),
                            "cold_to_short": round(float(cold_ratio), 2),
                        },
                    )
                )
                used_spots.append((cy, cx, "cold_ir"))
                break

    # ------------------------------------------------------------------
    # 5. 15-Year AllWISE Archive Drift Check (Past 2010 vs Present 2026)
    # ------------------------------------------------------------------
    if overlays and overlays.allwise and cg_stack_z is not None:
        ref_peaks = [
            p for p in _find_local_extrema(cg_stack_z, sign=1, threshold=5.0, radius=2)
            if _has_nan_hole_nearby(cg_mean, p[1], p[2], radius=2) < 2
            and not _near_existing(p[1], p[2], "variable", 2.0)
        ]
        # Prefer actual moving candidate coordinate if already detected
        mover_cands = [c for c in candidates if c.kind == "mover"]
        if mover_cands:
            ra_p, dec_p = mover_cands[0].ra, mover_cands[0].dec
            check_y, check_x = int(round(mover_cands[0].fits_y)), int(round(mover_cands[0].fits_x))
            ref_snr = mover_cands[0].snr
        elif ref_peaks:
            check_y, check_x = ref_peaks[0][1], ref_peaks[0][2]
            ra_p, dec_p = _pix_to_sky(wcs, float(check_x), float(check_y))
            ref_snr = float(cg_stack_z[check_y, check_x])
        else:
            ra_p = dec_p = ref_snr = None  # type: ignore[assignment]

        if ra_p is not None and dec_p is not None:
            nearest_d = min(_angsep_arcsec(ra_p, dec_p, w.ra, w.dec) for w in overlays.allwise)
            # Note AllWISE query radius is capped cleanly near target; also measure from field target center
            nearest_center = min(
                _angsep_arcsec(manifest.target.ra, manifest.target.dec, w.ra, w.dec)
                for w in overlays.allwise
            )
            eff_d = min(nearest_d, nearest_center) if not mover_cands else nearest_d
            if 7.5 <= eff_d <= 180.0:
                candidates.append(
                    PatternCandidate(
                        id="archive_drift_wise",
                        kind="archive_drift",
                        title=f"Moved Since 2010? (Nearest AllWISE Dot {eff_d:.1f}\" Away)",
                        summary=(
                            f"Nothing sat at this SPHEREx source's coordinate in NASA's 2010 AllWISE map "
                            f"(closest 2010 source is {eff_d:.1f}\" away) — clue of 15-year drift."
                        ),
                        confidence="Medium",
                        snr=round(float(ref_snr), 1),
                        ra=ra_p,
                        dec=dec_p,
                        fits_x=float(check_x),
                        fits_y=float(check_y),
                        suggested_label="Moving World",
                        metrics={"nearest_wise_arcsec": round(float(eff_d), 1)},
                    )
                )

    order_rank = {"mover": 0, "cold_ir": 1, "variable": 2, "archive_drift": 3}
    conf_rank = {"High": 0, "Medium": 1}
    candidates.sort(key=lambda c: (conf_rank.get(c.confidence, 9), order_rank.get(c.kind, 9), -c.snr))
    candidates = candidates[:4]

    if candidates:
        summary = f"Detected {len(candidates)} pattern clue(s) directly from pixel & catalog math: #1 '{candidates[0].title}'."
    else:
        summary = "No strong >4.5σ moving pairs, brightness swings, or thermal anomalies stand out above sky noise here."

    return PatternReport(
        session_id=manifest.session_id,
        n_patterns=len(candidates),
        summary=summary,
        past_label=past_label,
        present_label=present_label,
        candidates=candidates,
    )
