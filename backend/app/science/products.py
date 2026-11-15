"""Science display products and tensor bundling utilities."""

from dataclasses import dataclass
import numpy as np

from app.models import FrameMeta, StretchHint


def compute_stretch_hint(plane: np.ndarray, *, symmetric: bool = False) -> StretchHint:
    """Compute robust percentile or symmetric noise-scaled clip bounds for Canvas rendering."""
    vals = plane[np.isfinite(plane)]
    if vals.size == 0:
        return StretchHint(p_lo=-1.0, p_hi=1.0) if symmetric else StretchHint(p_lo=0.0, p_hi=1.0)

    if symmetric:
        med = float(np.median(vals))
        mad = float(np.median(np.abs(vals - med)))
        sigma = max(1.4826 * mad, float(np.percentile(np.abs(vals), 90)) * 0.3, 1e-6)
        bound = 5.0 * sigma
        return StretchHint(p_lo=-bound, p_hi=bound)

    p_lo = float(np.percentile(vals, 2.0))
    p_hi = float(np.percentile(vals, 99.5))
    if p_hi <= p_lo:
        p_hi = p_lo + 1.0
    return StretchHint(p_lo=p_lo, p_hi=p_hi)


def _center_mean(plane: np.ndarray) -> float | None:
    """Measure mean intensity in central aperture box."""
    h, w = plane.shape
    r = max(2, min(h, w) // 10)
    cy, cx = h // 2, w // 2
    box = plane[cy - r : cy + r + 1, cx - r : cx + r + 1]
    vals = box[np.isfinite(box)]
    return float(np.mean(vals)) if vals.size > 0 else None


@dataclass
class CompiledProduct:
    """Compiled binary tensor plus traceable frame metadata for one SFP1 file."""

    name: str
    frame_ids: list[str]
    data: np.ndarray
    flags: np.ndarray | None
    metas: list[FrameMeta]
    planes_per_frame: int
