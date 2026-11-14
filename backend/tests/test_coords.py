"""Tests for RA/Dec parsing, proper-motion propagation, and North-Up TAN grids."""

from astropy.time import Time
import pytest

from app.core.coords import make_grid, parse_coords, propagate, validate_fov
from app.core.errors import ExploreError
from app.core.presets import PRESETS


def test_parse_coords_decimal_and_sexagesimal() -> None:
    c1 = parse_coords("133.795129", "-7.245147")
    assert abs(c1.ra.deg - 133.795129) < 1e-6
    assert abs(c1.dec.deg - (-7.245147)) < 1e-6

    c2 = parse_coords("08h55m10.831s", "-7d14m42.53s")
    assert abs(c2.ra.deg - 133.795129) < 1e-4
    assert abs(c2.dec.deg - (-7.245147)) < 1e-4

    c3 = parse_coords("08h55m10.831s -7d14m42.53s")
    assert abs(c3.ra.deg - c2.ra.deg) < 1e-7


def test_parse_coords_rejects_bad_input() -> None:
    with pytest.raises(ExploreError) as exc:
        parse_coords("", "")
    assert exc.value.error_code == "BAD_COORDS"

    with pytest.raises(ExploreError):
        validate_fov(1.5)


def test_barnards_star_propagation_2026() -> None:
    """Propagated Barnard's Star to 2026.2 must land within 2 arcsec of expected position."""
    preset = PRESETS["barnards-star"]
    mjd_2026_2 = Time(2026.2, format="jyear", scale="utc").mjd
    pos = propagate(preset, mjd_2026_2)
    assert abs(pos.ra.deg - 269.44623) * 3600.0 < 2.0
    assert abs(pos.dec.deg - 4.76881) * 3600.0 < 2.0


def test_r_draconis_corrected_position() -> None:
    """R Draconis J2000 coordinates match 16h32m40.23s +66d45m17.9s."""
    preset = PRESETS["r-draconis"]
    assert abs(preset.ra_deg - 248.16761) < 1e-4
    assert abs(preset.dec_deg - 66.75498) < 1e-4


def test_make_grid_is_north_up_615() -> None:
    c = parse_coords("269.446", "4.768")
    spec, wcs = make_grid(c, 0.05)
    assert spec.north_up is True
    assert spec.npix == 29
    assert spec.pixscale_arcsec == 6.15
    assert wcs.wcs.cdelt[0] < 0  # East left
    assert wcs.wcs.cdelt[1] > 0  # North up
