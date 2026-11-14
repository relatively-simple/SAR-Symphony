"""Tests for FLAGS constants, compact remapping, ZODI subtraction, and masking."""

import numpy as np
from tests.conftest import make_test_wcs

from app.core.flags import (
    DICHROIC,
    MISSING_DATA,
    NONFUNC,
    OVERFLOW,
    SUR_ERROR,
    TRANSIENT,
    remap_raw_to_uint16,
    summarize_raw_flags,
    summarize_uint16_flags,
)
from app.science.clean import clean_subimage


def test_flag_remapping_and_summary() -> None:
    arr = np.array(
        [
            [0, TRANSIENT, OVERFLOW],
            [SUR_ERROR, NONFUNC, DICHROIC | MISSING_DATA],
        ],
        dtype=np.int32,
    )
    s_raw = summarize_raw_flags(arr)
    assert s_raw == {
        "TRANSIENT": 1,
        "OVERFLOW": 1,
        "SUR_ERROR": 1,
        "NONFUNC": 1,
        "DICHROIC": 1,
        "MISSING_DATA": 1,
    }
    u16 = remap_raw_to_uint16(arr)
    assert u16.dtype == np.uint16
    assert summarize_uint16_flags(u16) == s_raw


def test_clean_subtracts_zodi_and_masks_fatal_only() -> None:
    wcs = make_test_wcs(npix=5)
    raw = np.full((5, 5), 50.0, dtype=np.float32)
    raw[2, 2] = 150.0  # Star (+100 over sky)
    zodi = np.full((5, 5), 30.0, dtype=np.float32)
    flags = np.zeros((5, 5), dtype=np.int32)
    flags[0, 0] = NONFUNC       # fatal -> NaN
    flags[0, 1] = TRANSIENT     # warn only -> kept in image!
    flags[0, 2] = OVERFLOW      # fatal -> NaN
    flags[1, 0] = MISSING_DATA  # fatal -> NaN
    var = np.full((5, 5), 4.0, dtype=np.float32)

    cleaned = clean_subimage(
        obs_id="obs1",
        collection="spherex_dr1",
        detector=3,
        t_mid_mjd=61000.0,
        wavelength_um=2.0,
        raw_image=raw,
        raw_flags=flags,
        raw_variance=var,
        raw_zodi=zodi,
        wcs=wcs,
        subtract_residual_sky=False,
    )
    assert np.isnan(cleaned.image[0, 0])
    assert np.isnan(cleaned.image[0, 2])
    assert np.isnan(cleaned.image[1, 0])
    assert cleaned.image[0, 1] == pytest.approx(20.0)  # 50 - 30 kept
    assert cleaned.image[2, 2] == pytest.approx(120.0)  # 150 - 30 kept
    assert cleaned.flag_summary["TRANSIENT"] == 1
    assert cleaned.flag_summary["NONFUNC"] == 1
import pytest
