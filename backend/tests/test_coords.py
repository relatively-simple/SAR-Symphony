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


def test_kandy_floods_coordinates() -> None:
    """Verify Kandy Floods preset coordinates match central Sri Lanka."""
    preset = PRESETS["kandy-floods"]
    assert abs(preset.lon - 80.6337) < 1e-4
    assert abs(preset.lat - 7.2906) < 1e-4
    assert abs(preset.ra_deg - 80.6337) < 1e-4
    assert abs(preset.dec_deg - 7.2906) < 1e-4


def test_maui_wildfire_coordinates() -> None:
    """Verify Maui Wildfire coordinates match Lahaina, Hawaii."""
    preset = PRESETS["maui-wildfire"]
    assert abs(preset.lon - (-156.6825)) < 1e-4
    assert abs(preset.lat - 20.8783) < 1e-4


def test_make_grid_is_north_up_615() -> None:
    c = parse_coords("269.446", "4.768")
    spec, wcs = make_grid(c, 0.05)
    assert spec.north_up is True
    assert spec.npix == 29
    assert spec.pixscale_arcsec == 6.15
    assert wcs.wcs.cdelt[0] < 0  # East left
    assert wcs.wcs.cdelt[1] > 0  # North up
