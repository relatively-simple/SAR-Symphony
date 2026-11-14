"""Tests for inverse-variance coadding, static-star cancellation, and moving-star dipoles."""

import numpy as np
from tests.conftest import gaussian_star, make_test_wcs

from app.core.coords import make_grid, parse_coords
from app.models import ExposureRecord, SurveyPass
from app.science.align import align_frame
from app.science.clean import clean_subimage
from app.science.products import build_all_products


def _make_aligned(obs_id: str, det: int, mjd: float, star_x: float, star_y: float, flux: float = 100.0):
    center = parse_coords("200.0", "15.0")
    spec, grid_wcs = make_grid(center, 0.05)
    n = spec.npix
    raw_wcs = make_test_wcs(200.0, 15.0, npix=n)
    img = gaussian_star((n, n), star_x, star_y, flux=flux, sigma=1.1)
    # Add second static background star that should cancel identically in difference frame
    img += gaussian_star((n, n), 6.0, 6.0, flux=80.0, sigma=1.1)
    clean = clean_subimage(
        obs_id=obs_id,
        collection="spherex_dr1",
        detector=det,
        t_mid_mjd=mjd,
        wavelength_um=2.0,
        raw_image=img,
        raw_flags=np.zeros((n, n), dtype=np.int32),
        raw_variance=np.ones((n, n), dtype=np.float32),
        raw_zodi=np.zeros((n, n), dtype=np.float32),
        wcs=raw_wcs,
        subtract_residual_sky=False,
    )
    return align_frame(clean, grid_wcs, n)


def test_coadd_and_motion_dipole_vs_static_cancellation() -> None:
    passes = [
        SurveyPass(index=0, mjd_start=60800.0, mjd_end=60810.0, mjd_mid=60805.0, n_exposures=2, label="Pass 1"),
        SurveyPass(index=1, mjd_start=61000.0, mjd_end=61010.0, mjd_mid=61005.0, n_exposures=2, label="Pass 2"),
    ]
    pass_map = {("o1", 3): 0, ("o2", 3): 0, ("o3", 3): 1, ("o4", 3): 1}

    # Mover shifts from x=14 -> x=16 across passes while static star stays at (6, 6)
    frames = [
        _make_aligned("o1", 3, 60802.0, 14.0, 14.0),
        _make_aligned("o2", 3, 60808.0, 14.0, 14.0),
        _make_aligned("o3", 3, 61002.0, 16.0, 14.0),
        _make_aligned("o4", 3, 61008.0, 16.0, 14.0),
    ]
    prods = build_all_products(frames, pass_map, passes, 29)
    assert "pass_coadds" in prods
    assert "diffs" in prods

    diff = prods["diffs"].data[0, 0]
    # Static background star near (6, 6) cancels cleanly (~0)
    assert abs(float(diff[6, 6])) < 1.0
    # Moving star produces strong negative lobe near old position (14, 14) and positive lobe near new position (16, 14)
    assert float(diff[14, 13]) < -30.0 or float(diff[14, 14]) < -20.0
    assert float(diff[14, 16]) > 30.0


def test_coldglow_isolates_longwave_and_rgb_reddens_cold_source() -> None:
    passes = [
        SurveyPass(index=0, mjd_start=60800.0, mjd_end=60810.0, mjd_mid=60805.0, n_exposures=6, label="Pass 1"),
    ]
    center = parse_coords("200.0", "15.0")
    spec, grid_wcs = make_grid(center, 0.05)
    n = spec.npix
    raw_wcs = make_test_wcs(200.0, 15.0, npix=n)

    frames = []
    pass_map = {}
    # D1..D6: reference star at (6, 6) in all bands; cold Y-dwarf analogue at (14, 14) emits only in D5..D6.
    for det, lam in [(1, 0.9), (2, 1.3), (3, 2.0), (4, 3.2), (5, 4.1), (6, 4.7)]:
        img = gaussian_star((n, n), 6.0, 6.0, flux=60.0, sigma=1.0)
        if det in (5, 6):
            img += gaussian_star((n, n), 14.0, 14.0, flux=120.0, sigma=1.0)
        oid = f"cg_{det}"
        pass_map[(oid, det)] = 0
        clean = clean_subimage(
            obs_id=oid,
            collection="spherex_dr1",
            detector=det,
            t_mid_mjd=60805.0,
            wavelength_um=lam,
            raw_image=img,
            raw_flags=np.zeros((n, n), dtype=np.int32),
            raw_variance=np.ones((n, n), dtype=np.float32),
            raw_zodi=np.zeros((n, n), dtype=np.float32),
            wcs=raw_wcs,
            subtract_residual_sky=False,
        )
        frames.append(align_frame(clean, grid_wcs, n))

    prods = build_all_products(frames, pass_map, passes, n)
    assert "coldglow" in prods
    assert "rgb" in prods

    cg = prods["coldglow"].data[0, 0]
    assert float(cg[14, 14]) > 90.0

    rgb = prods["rgb"].data[0]
    assert rgb.shape == (3, n, n)
    # Cold source peaks in Red channel (D5+D6) vs Blue channel (D1+D2)
    assert float(rgb[0, 14, 14]) > float(rgb[2, 14, 14]) + 0.3
