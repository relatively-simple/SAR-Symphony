"""On-the-fly multi-detector aperture spectrum extraction using SPHEREx WCS-WAVE."""

import math
import numpy as np

from app.core.coords import PIXSCALE_ARCSEC
from app.core.flags import FATAL_MASK, OVERFLOW, SUR_ERROR, WARN_MASK
from app.models import SpectrumPoint, SpectrumResult


def _subimage_bg_subtracted(sub: dict) -> np.ndarray:
    """Return ZODI-subtracted Float32 image, reusing precomputed array when cached."""
    cached = sub.get("bg_sub")
    if cached is not None:
        return cached
    bg_sub = sub["image"].astype(np.float32) - sub["zodi"].astype(np.float32)
    sub["bg_sub"] = bg_sub
    return bg_sub


def _extract_with_radii(
    ra_deg: float,
    dec_deg: float,
    subimages: list[dict],
    *,
    aperture_px: float,
    annulus_inner_px: float,
    annulus_outer_px: float,
    allow_saturated_halo: bool,
) -> tuple[list[SpectrumPoint], int]:
    """Measure aperture flux across subimages with shared grid and WCS geometry."""
    points: list[SpectrumPoint] = []
    n_rejected = 0
    grid_cache: dict[tuple[int, int], tuple[np.ndarray, np.ndarray]] = {}
    ap_r2 = aperture_px**2
    ann_in2 = annulus_inner_px**2
    ann_out2 = annulus_outer_px**2
    core_r2 = min(1.0, aperture_px) ** 2
    non_sat_fatal_mask = FATAL_MASK & ~(OVERFLOW | SUR_ERROR)

    for sub in subimages:
        wcs = sub["wcs"]
        image = _subimage_bg_subtracted(sub)
        flags = sub["flags"].astype(np.int64, copy=False)
        var = sub["variance"].astype(np.float32, copy=False)
        wave_map = sub["wave_map"]
        meta = sub["meta"]

        ny, nx = image.shape
        px_arr, py_arr = wcs.world_to_pixel_values(ra_deg, dec_deg)
        px = float(np.asarray(px_arr).item())
        py = float(np.asarray(py_arr).item())

        if not (np.isfinite(px) and np.isfinite(py)) or px < 1.0 or py < 1.0 or px > nx - 2 or py > ny - 2:
            n_rejected += 1
            continue

        iy = int(np.clip(round(py), 0, ny - 1))
        ix = int(np.clip(round(px), 0, nx - 1))
        lam_um = float(wave_map[iy, ix])
        if not (np.isfinite(lam_um) and 0.5 < lam_um < 6.0):
            n_rejected += 1
            continue

        grid = grid_cache.get((ny, nx))
        if grid is None:
            grid = np.ogrid[:ny, :nx]
            grid_cache[(ny, nx)] = grid
        yy, xx = grid
        dist2 = (xx - px) ** 2 + (yy - py) ** 2

        fatal = (flags & FATAL_MASK) != 0
        valid = (~fatal) & np.isfinite(image) & np.isfinite(var) & (var > 0.0)
        ap_mask = dist2 <= ap_r2

        if allow_saturated_halo:
            core_flags = np.where(dist2 <= 1.2, flags, 0)
            if np.any((core_flags & non_sat_fatal_mask) != 0):
                n_rejected += 1
                continue
            use_mask = valid & ap_mask
            n_ap = int(np.count_nonzero(use_mask))
            if n_ap < 3:
                n_rejected += 1
                continue
            ann_mask = (dist2 >= ann_in2) & (dist2 <= ann_out2) & valid
            sky_bg = float(np.median(image[ann_mask])) if int(np.count_nonzero(ann_mask)) >= 6 else 0.0
            flagged = True
        else:
            if not np.any(ap_mask):
                n_rejected += 1
                continue
            core_mask = dist2 <= core_r2
            if np.any(fatal & core_mask) or int(np.count_nonzero(valid & ap_mask)) < 2:
                n_rejected += 1
                continue
            ann_mask = (dist2 >= ann_in2) & (dist2 <= ann_out2) & valid
            if int(np.count_nonzero(ann_mask)) >= 6:
                sky_bg = float(np.median(image[ann_mask]))
            elif np.any(valid):
                sky_bg = float(np.median(image[valid]))
            else:
                sky_bg = 0.0
            use_mask = valid & ap_mask
            n_ap = int(np.count_nonzero(use_mask))
            flagged = bool(np.any(((flags & WARN_MASK) != 0) & ap_mask))

        mean_flux = float(np.mean(image[use_mask] - sky_bg))
        err = float(np.sqrt(np.sum(var[use_mask])) / n_ap)

        points.append(
            SpectrumPoint(
                wavelength_um=round(lam_um, 4),
                flux_mjysr=round(mean_flux, 5),
                err=round(err, 5),
                detector=int(meta["detector"]),
                mjd=float(meta["t_mid_mjd"]),
                obs_id=str(meta["obs_id"]),
                flagged=flagged,
            )
        )

    points.sort(key=lambda p: (p.wavelength_um, p.mjd))
    return points, n_rejected


def _build_halo_result(
    ra_deg: float,
    dec_deg: float,
    points: list[SpectrumPoint],
    n_rejected: int,
    aperture_px: float,
) -> SpectrumResult:
    return SpectrumResult(
        ra=round(ra_deg, 6),
        dec=round(dec_deg, 6),
        points=points,
        aperture_arcsec=round(aperture_px * PIXSCALE_ARCSEC, 1),
        n_used=len(points),
        n_rejected=n_rejected,
        note=(
            "Bright source saturates central pixel(s) [OVERFLOW]; "
            "spectrum shows unmasked PSF halo photometry (lower limit). "
            "Click away from core for unsaturated field stars."
        ),
    )


def extract_spectrum_at(
    ra_deg: float,
    dec_deg: float,
    subimages: list[dict],
    *,
    aperture_px: float = 1.5,
    annulus_inner_px: float = 3.0,
    annulus_outer_px: float = 6.0,
) -> SpectrumResult:
    """Measure background-subtracted flux (MJy/sr) vs wavelength (um) across visits."""
    if not (math.isfinite(ra_deg) and math.isfinite(dec_deg)):
        return SpectrumResult(
            ra=0.0,
            dec=0.0,
            points=[],
            aperture_arcsec=round(aperture_px * PIXSCALE_ARCSEC, 1),
            n_used=0,
            n_rejected=0,
            note="Invalid non-finite coordinates.",
        )

    points, n_rejected = _extract_with_radii(
        ra_deg,
        dec_deg,
        subimages,
        aperture_px=aperture_px,
        annulus_inner_px=annulus_inner_px,
        annulus_outer_px=annulus_outer_px,
        allow_saturated_halo=False,
    )

    if (len(points) <= 3 and n_rejected >= 15) or (not points and n_rejected > 0):
        best: SpectrumResult | None = None
        for halo_ap, ann_in, ann_out in ((3.2, 4.5, 8.0), (4.8, 6.5, 10.0)):
            h_pts, h_rej = _extract_with_radii(
                ra_deg,
                dec_deg,
                subimages,
                aperture_px=halo_ap,
                annulus_inner_px=ann_in,
                annulus_outer_px=ann_out,
                allow_saturated_halo=True,
            )
            if h_pts and (best is None or len(h_pts) > best.n_used):
                best = _build_halo_result(ra_deg, dec_deg, h_pts, h_rej, halo_ap)
            if best is not None and best.n_used >= 8:
                break
            if not (len(points) <= 3 and n_rejected >= 15):
                break
        if best is not None and (best.n_used > len(points) or not points):
            return best

    note = None
    if n_rejected > 0 and points:
        if n_rejected > len(points) * 3 and n_rejected >= 15:
            note = (
                f"{n_rejected} visit(s) excluded (edge, FATAL flags, or bright-star OVERFLOW saturation). "
                "Tip: click 1-2 px off-center to sample unsaturated PSF wings across all 6 detectors."
            )
        else:
            note = f"{n_rejected} visit(s) excluded near detector edge or masked by FATAL quality flags."
    elif not points:
        note = "No unmasked visits cover this clicked coordinate."

    return SpectrumResult(
        ra=round(ra_deg, 6),
        dec=round(dec_deg, 6),
        points=points,
        aperture_arcsec=round(aperture_px * PIXSCALE_ARCSEC, 1),
        n_used=len(points),
        n_rejected=n_rejected,
        note=note,
    )
