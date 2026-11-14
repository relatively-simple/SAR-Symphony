"""ZODI foreground subtraction, FLAGS bitmask cleaning, and background estimation."""

from dataclasses import dataclass
import numpy as np
from astropy.wcs import WCS

from app.core.flags import FATAL_MASK, remap_raw_to_uint16, summarize_raw_flags


@dataclass
class CleanFrame:
    """Calibrated single exposure ready for astrometric reprojection."""

    obs_id: str
    collection: str
    detector: int
    t_mid_mjd: float
    wavelength_um: float
    image: np.ndarray        # float32 (ny, nx), NaN where masked
    variance: np.ndarray     # float32 (ny, nx), inf where masked
    flags_u16: np.ndarray    # uint16 (ny, nx), compact bits 0..5
    flag_summary: dict[str, int]
    wcs: WCS


def clean_subimage(
    *,
    obs_id: str,
    collection: str,
    detector: int,
    t_mid_mjd: float,
    wavelength_um: float,
    raw_image: np.ndarray,
    raw_flags: np.ndarray,
    raw_variance: np.ndarray,
    raw_zodi: np.ndarray,
    wcs: WCS,
    subtract_residual_sky: bool = True,
) -> CleanFrame:
    """Apply SPHEREx ZODI subtraction, FATAL pixel masking, and optional sky-median leveling."""
    zodi_free = raw_image.astype(np.float32) - raw_zodi.astype(np.float32)
    var = raw_variance.astype(np.float32, copy=True)

    fatal = (raw_flags.astype(np.int64, copy=False) & FATAL_MASK) != 0
    invalid = fatal | (~np.isfinite(zodi_free)) | (~np.isfinite(var)) | (var <= 0.0)

    zodi_free[invalid] = np.nan
    var[invalid] = np.inf

    if subtract_residual_sky:
        valid_vals = zodi_free[~invalid]
        if valid_vals.size > 0:
            zodi_free = zodi_free - np.float32(np.median(valid_vals))

    return CleanFrame(
        obs_id=obs_id,
        collection=collection,
        detector=detector,
        t_mid_mjd=t_mid_mjd,
        wavelength_um=wavelength_um,
        image=zodi_free,
        variance=var,
        flags_u16=remap_raw_to_uint16(raw_flags),
        flag_summary=summarize_raw_flags(raw_flags),
        wcs=wcs,
    )
