"""Inverse-variance weighted coaddition of aligned SPHEREx frames."""

from dataclasses import dataclass
import numpy as np

from app.core.flags import COMPACT_BITS, summarize_uint16_flags
from app.science.align import AlignedFrame


_MISSING_BIT = 1 << next(pos for pos, name, _ in COMPACT_BITS if name == "MISSING_DATA")


@dataclass
class CoaddResult:
    """Inverse-variance combined image cube for a pass/band bucket."""

    image: np.ndarray
    ivar: np.ndarray
    flags_u16: np.ndarray
    flag_summary: dict[str, int]
    mjd_mid: float
    wavelength_um: float
    obs_ids: list[str]
    n_inputs: int


def coadd_ivar(frames: list[AlignedFrame], sigma_clip: float = 4.0) -> CoaddResult:
    """Combine aligned frames using inverse-variance weights with cosmic-ray outlier clipping."""
    if not frames:
        raise ValueError("Cannot coadd empty frame list")

    shape = frames[0].image.shape
    imgs = np.stack([f.image for f in frames], axis=0).astype(np.float64)
    ivars = np.stack([f.ivar for f in frames], axis=0).astype(np.float64)
    flags_stack = np.stack([f.flags_u16 for f in frames], axis=0)

    valid = np.isfinite(imgs) & np.isfinite(ivars) & (ivars > 0.0)
    weights = np.where(valid, ivars, 0.0)

    # Mild outlier rejection (cosmic-ray protection) when >= 3 valid samples exist per pixel
    if len(frames) >= 3:
        masked_vals = np.where(valid, imgs, np.nan)
        med = np.nanmedian(masked_vals, axis=0)
        mad = np.nanmedian(np.abs(masked_vals - med[None, :, :]), axis=0)
        sigma = np.maximum(1.4826 * mad, np.sqrt(1.0 / np.maximum(np.nanmedian(np.where(valid, ivars, np.nan), axis=0), 1e-12)))
        outlier = valid & (np.sum(valid, axis=0)[None, :, :] >= 3) & (np.abs(imgs - med[None, :, :]) > sigma_clip * sigma[None, :, :])
        weights = np.where(outlier, 0.0, weights)

    w_sum = np.sum(weights, axis=0)
    good = w_sum > 0.0
    num = np.sum(np.where(weights > 0.0, weights * imgs, 0.0), axis=0)

    out_img = np.where(good, num / np.where(good, w_sum, 1.0), np.nan).astype(np.float32)
    out_ivar = w_sum.astype(np.float32)

    # Combine warn/fatal bits only across contributing frames; mark unpopulated pixels missing
    used = weights > 0.0
    out_flags = np.bitwise_or.reduce(np.where(used, flags_stack, np.uint16(0)), axis=0).astype(np.uint16)
    out_flags[~good] |= np.uint16(_MISSING_BIT)

    return CoaddResult(
        image=out_img,
        ivar=out_ivar,
        flags_u16=out_flags,
        flag_summary=summarize_uint16_flags(out_flags),
        mjd_mid=float(np.mean([f.t_mid_mjd for f in frames])),
        wavelength_um=float(np.mean([f.wavelength_um for f in frames])),
        obs_ids=[f.obs_id for f in frames],
        n_inputs=len(frames),
    )
