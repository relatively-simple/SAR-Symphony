"""Tests for WCS-WAVE aperture spectrum extraction and SFP1 binary round-trip."""

import numpy as np
from tests.conftest import gaussian_star, make_test_wcs

from app.core.flags import NONFUNC, OVERFLOW
from app.io.framepack import decode_framepack, encode_framepack
from app.science.spectrum import extract_spectrum_at


def test_extract_spectrum_recovers_flux_and_drops_fatal() -> None:
    wcs = make_test_wcs(200.0, 15.0, npix=25)
    subs = []
    for det, lam, flux in [(2, 1.45, 50.0), (5, 4.15, 220.0), (6, 4.65, 180.0)]:
        img = np.full((25, 25), 12.0, dtype=np.float32) + gaussian_star((25, 25), 12.0, 12.0, flux=flux, sigma=0.7)
        zodi = np.full((25, 25), 7.0, dtype=np.float32)
        flags = np.zeros((25, 25), dtype=np.int32)
        if det == 6:
            flags[12, 12] = NONFUNC  # Core poisoned -> visit must be rejected cleanly
        subs.append(
            {
                "wcs": wcs,
                "image": img,
                "zodi": zodi,
                "flags": flags,
                "variance": np.full((25, 25), 1.0, dtype=np.float32),
                "wave_map": np.full((25, 25), lam, dtype=np.float32),
                "meta": {"detector": det, "t_mid_mjd": 61000.0, "obs_id": f"obs_{det}"},
            }
        )

    res = extract_spectrum_at(200.0, 15.0, subs)
    assert res.n_used == 2
    assert res.n_rejected == 1
    assert [p.detector for p in res.points] == [2, 5]
    assert res.points[1].flux_mjysr > res.points[0].flux_mjysr
    assert res.points[0].wavelength_um == 1.45
    assert res.points[1].wavelength_um == 4.15


def test_sfp1_framepack_roundtrip() -> None:
    data = np.arange(2 * 3 * 5 * 5, dtype=np.float32).reshape((2, 3, 5, 5))
    data[0, 1, 2, 2] = np.nan
    flags = np.ones((2, 5, 5), dtype=np.uint16) * 7
    blob = encode_framepack(["f0", "f1"], data, flags)
    hdr, out_d, out_f = decode_framepack(blob)

    assert hdr["frame_ids"] == ["f0", "f1"]
    assert hdr["planes_per_frame"] == 3
    assert hdr["npix"] == 5
    assert np.allclose(out_d, data, equal_nan=True)
    assert out_f is not None and np.array_equal(out_f, flags)


def test_extract_spectrum_saturated_overflow_halo_fallback() -> None:
    wcs = make_test_wcs(150.0, -10.0, npix=25)
    img = np.full((25, 25), 5.0, dtype=np.float32) + gaussian_star((25, 25), 12.0, 12.0, flux=80.0, sigma=1.4)
    flags = np.zeros((25, 25), dtype=np.int32)
    flags[11:14, 11:14] = OVERFLOW  # Entire central core saturated

    sub = {
        "wcs": wcs,
        "image": img,
        "zodi": np.full((25, 25), 2.0, dtype=np.float32),
        "flags": flags,
        "variance": np.full((25, 25), 0.25, dtype=np.float32),
        "wave_map": np.full((25, 25), 4.2, dtype=np.float32),
        "meta": {"detector": 5, "t_mid_mjd": 61000.0, "obs_id": "sat_obs"},
    }
    res = extract_spectrum_at(150.0, -10.0, [sub])
    assert res.n_used == 1
    assert res.points[0].flagged is True
    assert res.points[0].flux_mjysr > 0.0
    assert "OVERFLOW" in (res.note or "")
