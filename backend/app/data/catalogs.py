"""Gaia DR3 & AllWISE cross-mission catalog overlays with proper-motion propagation."""

import asyncio
import csv
import io
import json
import math
from pathlib import Path
from astropy.time import Time
import httpx

from app.data.http import request_with_retry
from app.models import AllwiseSource, GaiaSource, OverlaySet


GATOR_URL = "https://irsa.ipac.caltech.edu/cgi-bin/Gator/nph-query"
GAIA_TAP_URL = "https://gea.esac.esa.int/tap-server/tap/sync"


def propagate_gaia_position(
    ra_2016: float,
    dec_2016: float,
    pmra_masyr: float | None,
    pmdec_masyr: float | None,
    mjd_target: float,
) -> tuple[float, float]:
    """Propagate a Gaia DR3 J2016.0 position to `mjd_target` using linear PM."""
    if pmra_masyr is None or pmdec_masyr is None or (pmra_masyr == 0.0 and pmdec_masyr == 0.0):
        return ra_2016, dec_2016
    dt_years = (Time(mjd_target, format="mjd", scale="utc").jyear) - 2016.0
    cosd = max(math.cos(math.radians(dec_2016)), 0.05)
    dra_deg = (pmra_masyr / 1000.0) * dt_years / 3600.0 / cosd
    ddec_deg = (pmdec_masyr / 1000.0) * dt_years / 3600.0
    return (ra_2016 + dra_deg) % 360.0, max(-90.0, min(90.0, dec_2016 + ddec_deg))


def _parse_gator_ipac_table(text: str) -> list[dict[str, str]]:
    """Parse IRSA Gator fixed-width IPAC ASCII table rows safely even when null cells are blank."""
    cols: list[str] = []
    bounds: list[tuple[int, int]] = []
    rows: list[dict[str, str]] = []
    for line in text.splitlines():
        if line.startswith("|") and not cols:
            pipes = [idx for idx, ch in enumerate(line) if ch == "|"]
            for i in range(len(pipes) - 1):
                cols.append(line[pipes[i] + 1 : pipes[i + 1]].strip())
                bounds.append((pipes[i] + 1, pipes[i + 1]))
            continue
        if not line or line[0] in ("\\", "|"):
            continue
        if cols and bounds:
            row = {cols[i]: line[lo:hi].strip() for i, (lo, hi) in enumerate(bounds)}
            rows.append(row)
    return rows


def _opt_float(val: str | None) -> float | None:
    if val is None or val in ("", "null", "NaN", "nan", "---"):
        return None
    try:
        num = float(val)
        return num if math.isfinite(num) else None
    except ValueError:
        return None


async def fetch_allwise_cone(
    client: httpx.AsyncClient,
    ra_deg: float,
    dec_deg: float,
    radius_arcsec: float,
    max_sources: int = 80,
) -> list[AllwiseSource]:
    """Query IRSA AllWISE Source Catalog via fast Gator cone search."""
    resp = await request_with_retry(
        client,
        "GET",
        GATOR_URL,
        params={
            "catalog": "allwise_p3as_psd",
            "spatial": "cone",
            "objstr": f"{ra_deg:.6f} {dec_deg:.6f}",
            "radius": f"{min(900.0, radius_arcsec):.1f}",
            "outfmt": "1",
            "selcols": "designation,ra,dec,w1mpro,w2mpro",
        },
        max_attempts=2,
    )
    rows = _parse_gator_ipac_table(resp.text)
    out: list[AllwiseSource] = []
    for r in rows[:max_sources]:
        ra = _opt_float(r.get("ra"))
        dec = _opt_float(r.get("dec"))
        if ra is None or dec is None:
            continue
        out.append(
            AllwiseSource(
                designation=r.get("designation", ""),
                ra=ra,
                dec=dec,
                w1=_opt_float(r.get("w1mpro")),
                w2=_opt_float(r.get("w2mpro")),
            )
        )
    return out


async def fetch_gaia_cone(
    client: httpx.AsyncClient,
    ra_deg: float,
    dec_deg: float,
    radius_arcsec: float,
    mjd_ref: float,
    max_sources: int = 80,
) -> list[GaiaSource]:
    """Fetch Gaia DR3 sources via IRSA Gator `gaia_dr3_source`, falling back to ESA Gaia TAP."""
    out: list[GaiaSource] = []
    try:
        resp = await request_with_retry(
            client,
            "GET",
            GATOR_URL,
            params={
                "catalog": "gaia_dr3_source",
                "spatial": "cone",
                "objstr": f"{ra_deg:.6f} {dec_deg:.6f}",
                "radius": f"{min(900.0, radius_arcsec):.1f}",
                "outfmt": "1",
                "selcols": "source_id,ra,dec,pmra,pmdec,phot_g_mean_mag",
            },
            max_attempts=2,
        )
        rows = _parse_gator_ipac_table(resp.text)
        for row in rows:
            ra = _opt_float(row.get("ra"))
            dec = _opt_float(row.get("dec"))
            if ra is None or dec is None:
                continue
            pmra = _opt_float(row.get("pmra"))
            pmdec = _opt_float(row.get("pmdec"))
            g_mag = _opt_float(row.get("phot_g_mean_mag"))
            ra_now, dec_now = propagate_gaia_position(ra, dec, pmra, pmdec, mjd_ref)
            out.append(
                GaiaSource(
                    source_id=str(row.get("source_id", "")),
                    ra=ra,
                    dec=dec,
                    g_mag=g_mag,
                    pmra=pmra,
                    pmdec=pmdec,
                    ra_at_mjd=round(ra_now, 7),
                    dec_at_mjd=round(dec_now, 7),
                )
            )
        if out:
            out.sort(key=lambda s: s.g_mag if s.g_mag is not None else 99.0)
            return out[:max_sources]
    except Exception:
        pass

    radius_deg = min(0.25, max(0.01, radius_arcsec / 3600.0))
    adql = (
        f"SELECT TOP {int(max_sources)} source_id,ra,dec,pmra,pmdec,phot_g_mean_mag "
        f"FROM gaiadr3.gaia_source "
        f"WHERE 1=CONTAINS(POINT(ra,dec), CIRCLE({ra_deg:.6f},{dec_deg:.6f},{radius_deg:.5f})) "
        f"ORDER BY phot_g_mean_mag ASC"
    )
    resp = await request_with_retry(
        client,
        "GET",
        GAIA_TAP_URL,
        params={"REQUEST": "doQuery", "LANG": "ADQL", "FORMAT": "csv", "QUERY": adql},
        max_attempts=2,
    )
    reader = csv.DictReader(io.StringIO(resp.text))
    for row in reader:
        ra = _opt_float(row.get("ra"))
        dec = _opt_float(row.get("dec"))
        if ra is None or dec is None:
            continue
        pmra = _opt_float(row.get("pmra"))
        pmdec = _opt_float(row.get("pmdec"))
        ra_now, dec_now = propagate_gaia_position(ra, dec, pmra, pmdec, mjd_ref)
        out.append(
            GaiaSource(
                source_id=str(row.get("source_id", "")),
                ra=ra,
                dec=dec,
                g_mag=_opt_float(row.get("phot_g_mean_mag")),
                pmra=pmra,
                pmdec=pmdec,
                ra_at_mjd=round(ra_now, 7),
                dec_at_mjd=round(dec_now, 7),
            )
        )
    return out


def repropagate_overlays(ov: OverlaySet, mjd_ref: float | None) -> OverlaySet:
    """Update Gaia J2016 positions dynamically if requested epoch differs by > 1 day."""
    if mjd_ref is not None and abs(mjd_ref - ov.mjd_ref) > 1.0:
        for g in ov.gaia:
            g.ra_at_mjd, g.dec_at_mjd = propagate_gaia_position(g.ra, g.dec, g.pmra, g.pmdec, mjd_ref)
        ov.mjd_ref = mjd_ref
    return ov


def load_preset_overlays(preset_dir: Path, slug: str, mjd_ref: float | None = None) -> OverlaySet | None:
    """Load pre-baked catalog overlays cleanly and re-propagate Gaia if mjd_ref differs."""
    p = preset_dir / slug / "overlays.json"
    if not p.exists():
        return None
    data = json.loads(p.read_text(encoding="utf-8"))
    return repropagate_overlays(OverlaySet.model_validate(data), mjd_ref)


async def query_live_overlays(
    client: httpx.AsyncClient,
    ra_deg: float,
    dec_deg: float,
    fov_deg: float,
    mjd_ref: float,
) -> OverlaySet:
    """Best-effort concurrent Gaia DR3 + AllWISE query with graceful fallback when throttled."""
    radius_arcsec = max(30.0, fov_deg * 3600.0 * 0.75)
    allwise_res, gaia_res = await asyncio.gather(
        fetch_allwise_cone(client, ra_deg, dec_deg, radius_arcsec),
        fetch_gaia_cone(client, ra_deg, dec_deg, radius_arcsec, mjd_ref),
        return_exceptions=True,
    )

    notes: list[str] = []
    if isinstance(allwise_res, Exception):
        allwise: list[AllwiseSource] = []
        notes.append("AllWISE catalog unreachable.")
    else:
        allwise = allwise_res

    if isinstance(gaia_res, Exception):
        gaia: list[GaiaSource] = []
        notes.append("Gaia DR3 catalog temporarily throttled; use Aladin inset for interactive Gaia stars.")
    else:
        gaia = gaia_res

    src = "live" if (gaia or allwise) else "unavailable"
    return OverlaySet(
        gaia=gaia,
        allwise=allwise,
        source=src,
        mjd_ref=mjd_ref,
        note=" ".join(notes) if notes else None,
    )
