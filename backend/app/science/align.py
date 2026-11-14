"""Astrometric reprojection onto the shared North-Up TAN WCS grid."""

from dataclasses import dataclass
import numpy as np
from astropy.wcs import WCS
from reproject import reproject_interp

from app.core.flags import COMPACT_BITS
from app.science.clean import CleanFrame


# Compact bit position 5 corresponds to MISSING_DATA
_MISSING_BIT = 1 << next(pos for pos, name, _ in COMPACT_BITS if name == "MISSING_DATA")


@dataclass
class AlignedFrame:
    """Single exposure aligned onto the target's shared North-Up TAN grid."""

    obs_id: str
    collection: str
    detector: int
    t_mid_mjd: float
    wavelength_um: float
    image: np.ndarray        # float32 (npix, npix)
    ivar: np.ndarray         # float32 inverse variance (npix, npix), 0 where invalid
    flags_u16: np.ndarray    # uint16 (npix, npix)
    flag_summary: dict[str, int]


def align_frame(frame: CleanFrame, grid_wcs: WCS, npix: int) -> AlignedFrame:
    """Reproject science image, inverse-variance map, and bitmask onto shared TAN grid."""
    shape_out = (npix, npix)

    proj_img, footprint = reproject_interp(
        (frame.image, frame.wcs),
        grid_wcs,
        shape_out=shape_out,
        order="bilinear",
        roundtrip_coords=False,
    )

    valid_in = np.isfinite(frame.image) & np.isfinite(frame.variance) & (frame.variance > 0.0)
    ivar_in = np.where(valid_in, 1.0 / frame.variance, 0.0).astype(np.float32)
    proj_ivar, _ = reproject_interp(
        (ivar_in, frame.wcs),
        grid_wcs,
        shape_out=shape_out,
        order="bilinear",
        roundtrip_coords=False,
    )

    proj_flags_f, _ = reproject_interp(
        (frame.flags_u16.astype(np.float32), frame.wcs),
        grid_wcs,
        shape_out=shape_out,
        order="nearest-neighbor",
        roundtrip_coords=False,
    )
    proj_flags = np.where(np.isfinite(proj_flags_f), np.rint(proj_flags_f), _MISSING_BIT).astype(np.uint16)

    out_valid = np.isfinite(proj_img) & np.isfinite(proj_ivar) & (proj_ivar > 0.0) & (footprint > 0.5)
    clean_img = np.where(out_valid, proj_img, np.nan).astype(np.float32)
    clean_ivar = np.where(out_valid, proj_ivar, 0.0).astype(np.float32)
    proj_flags[~out_valid] |= np.uint16(_MISSING_BIT)

    return AlignedFrame(
        obs_id=frame.obs_id,
        collection=frame.collection,
        detector=frame.detector,
        t_mid_mjd=frame.t_mid_mjd,
        wavelength_um=frame.wavelength_um,
        image=clean_img,
        ivar=clean_ivar,
        flags_u16=proj_flags,
        flag_summary=frame.flag_summary,
    )
