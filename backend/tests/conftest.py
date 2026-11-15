"""Shared pytest fixtures and test helpers for offline SAR Symphony verification."""

import sys
from pathlib import Path
import numpy as np
import pytest
from astropy.wcs import WCS

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


def make_test_wcs(ra0: float = 200.0, dec0: float = 15.0, npix: int = 31, pixscale_arcsec: float = 6.15) -> WCS:
    """Create deterministic North-Up TAN WCS centered on (ra0, dec0)."""
    w = WCS(naxis=2)
    w.wcs.ctype = ["RA---TAN", "DEC--TAN"]
    w.wcs.crval = [ra0, dec0]
    w.wcs.crpix = [(npix + 1) / 2.0, (npix + 1) / 2.0]
    cdelt = pixscale_arcsec / 3600.0
    w.wcs.cdelt = [-cdelt, cdelt]
    return w


def gaussian_star(shape: tuple[int, int], cx: float, cy: float, flux: float = 100.0, sigma: float = 1.0) -> np.ndarray:
    """Render a clean 2D Gaussian spatial feature centered at floating pixel (cx, cy)."""
    ny, nx = shape
    yy, xx = np.mgrid[0:ny, 0:nx]
    return (flux * np.exp(-((xx - cx) ** 2 + (yy - cy) ** 2) / (2.0 * sigma**2))).astype(np.float32)


@pytest.fixture
def tmp_cache_dir(tmp_path: Path) -> Path:
    return tmp_path / "cache"
