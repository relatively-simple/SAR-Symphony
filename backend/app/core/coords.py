"""Coordinate parsing, epoch alignment, and North-Up TAN grid generation."""

import re
import astropy.units as u
from astropy.coordinates import SkyCoord
from astropy.time import Time
from astropy.wcs import WCS

from app.core.errors import ExploreError
from app.models import GridSpec, SurveyPass, TargetPreset


ALLOWED_FOVS = (0.05, 0.1, 0.25)
PIXSCALE_ARCSEC = 6.15


def parse_coords(ra_str: str, dec_str: str | None = None) -> SkyCoord:
    """Parse RA/Dec in decimal degrees or sexagesimal strings into ICRS SkyCoord.

    Supports formats such as:
    - ra='133.795129', dec='-7.245147'
    - ra='08h55m10.831s', dec='-7d14m42.53s'
    - ra='08:55:10.831 -07:14:42.53' (combined into ra_str when dec_str is empty)
    """
    raw_ra = (ra_str or "").strip()
    raw_dec = (dec_str or "").strip()

    if not raw_ra:
        raise ExploreError("BAD_COORDS", "Enter Right Ascension and Declination coordinates.", 400)

    # Allow single-box combined input like "133.795 -7.245" or "08h55m10.8s -7d14m42.5s"
    if not raw_dec:
        if "," in raw_ra:
            parts = [p.strip() for p in raw_ra.split(",", 1)]
        else:
            parts = raw_ra.split()
        if len(parts) == 2:
            raw_ra, raw_dec = parts[0], parts[1]
        else:
            raise ExploreError(
                "BAD_COORDS",
                "Could not split coordinates. Use 'RA, Dec' like '133.795, -7.245' or '08h55m10.8s -7d14m42.5s'.",
                400,
            )

    # Normalize NASA's "-7d14m42.53s" / "+04°41'36\"" variants cleanly for Astropy
    norm_ra = raw_ra.replace("°", "d").replace("′", "m").replace("″", "s").replace("'", "m").replace('"', "s")
    norm_dec = raw_dec.replace("°", "d").replace("′", "m").replace("″", "s").replace("'", "m").replace('"', "s")

    try:
        is_decimal = _looks_decimal(norm_ra) and _looks_decimal(norm_dec)
        if is_decimal:
            coord = SkyCoord(ra=float(norm_ra) * u.deg, dec=float(norm_dec) * u.deg, frame="icrs")
        else:
            coord = SkyCoord(norm_ra, norm_dec, unit=(u.hourangle, u.deg), frame="icrs")
    except Exception as exc:
        raise ExploreError(
            "BAD_COORDS",
            f"Invalid coordinates '{raw_ra} {raw_dec}': {exc}",
            400,
        ) from exc

    if not (-90.0 <= coord.dec.deg <= 90.0) or not (0.0 <= coord.ra.deg < 360.0):
        raise ExploreError("BAD_COORDS", "Coordinates out of valid sky bounds (RA 0..360, Dec -90..+90).", 400)
    return coord


def _looks_decimal(val: str) -> bool:
    return bool(re.fullmatch(r"[+-]?(\d+(\.\d*)?|\.\d+)([eE][+-]?\d+)?", val))


def validate_fov(fov_deg: float) -> float:
    """Ensure requested FOV is bounded safely for live web fetching."""
    if fov_deg <= 0 or fov_deg > 0.30:
        raise ExploreError(
            "FOV_TOO_LARGE",
            f"Requested FOV {fov_deg}° must be between 0.02° and 0.25°.",
            400,
        )
    return float(fov_deg)


def propagate(preset: TargetPreset, mjd: float) -> SkyCoord:
    """Propagate a benchmark preset reference location cleanly to target MJD."""
    import warnings
    from erfa import ErfaWarning

    obstime = Time(preset.ref_epoch, format="jyear", scale="tcb")
    target_time = Time(mjd, format="mjd", scale="utc")

    if preset.pmra_masyr is None or preset.pmdec_masyr is None:
        return SkyCoord(ra=preset.ra_deg * u.deg, dec=preset.dec_deg * u.deg, frame="icrs")

    coord = SkyCoord(
        ra=preset.ra_deg * u.deg,
        dec=preset.dec_deg * u.deg,
        pm_ra_cosdec=preset.pmra_masyr * u.mas / u.yr,
        pm_dec=preset.pmdec_masyr * u.mas / u.yr,
        obstime=obstime,
        frame="icrs",
    )
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", ErfaWarning)
        return coord.apply_space_motion(new_obstime=target_time)


def mid_epoch(passes: list[SurveyPass]) -> float:
    """Compute midpoint MJD across survey passes."""
    if not passes:
        return Time.now().mjd
    return 0.5 * (passes[0].mjd_start + passes[-1].mjd_end)


def make_grid(center: SkyCoord, fov_deg: float, pixscale_arcsec: float = PIXSCALE_ARCSEC) -> tuple[GridSpec, WCS]:
    """Create a North-Up (N +Y, E -X) gnomonic TAN WCS grid centered at `center`."""
    npix = int(round((fov_deg * 3600.0) / pixscale_arcsec))
    npix = max(21, min(181, npix))
    if npix % 2 == 0:
        npix += 1  # Keep exact central pixel alignment cleanly

    cdelt_deg = pixscale_arcsec / 3600.0
    wcs = WCS(naxis=2)
    wcs.wcs.ctype = ["RA---TAN", "DEC--TAN"]
    wcs.wcs.crval = [float(center.ra.deg), float(center.dec.deg)]
    wcs.wcs.crpix = [(npix + 1) / 2.0, (npix + 1) / 2.0]
    # North up (+Y), East left (-X) in standard projected convention
    wcs.wcs.cdelt = [-cdelt_deg, cdelt_deg]

    spec = GridSpec(
        ra0=float(center.ra.deg),
        dec0=float(center.dec.deg),
        fov_deg=float(fov_deg),
        npix=npix,
        pixscale_arcsec=pixscale_arcsec,
        ctype=("RA---TAN", "DEC--TAN"),
        north_up=True,
    )
    return spec, wcs
