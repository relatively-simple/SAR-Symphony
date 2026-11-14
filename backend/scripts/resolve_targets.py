"""Phase 0 verification script: resolve exact positions, reference epochs, and proper motions
for all 5 NASA Challenge 12 benchmark targets using SIMBAD TAP and IRSA Catalogs, then check
live SPHEREx DR1+QR3 pass coverage at their propagated 2025-2026 positions.
"""

import asyncio
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import astropy.units as u
from astropy.coordinates import SkyCoord
from astropy.time import Time

from app.data.http import create_async_client, request_with_retry
from app.data.planner import group_passes
from app.data.sia import query as query_sia


SIMBAD_TAP = "https://simbad.u-strasbg.fr/simbad/sim-tap/sync"
GATOR_URL = "https://irsa.ipac.caltech.edu/cgi-bin/Gator/nph-query"


async def simbad_lookup(client, name: str) -> dict | None:
    """Query SIMBAD basic table via ADQL TAP for ICRS J2000 position + proper motion."""
    safe = name.replace("'", "''")
    adql = (
        "SELECT TOP 1 b.main_id, b.ra, b.dec, b.pmra, b.pmdec, b.coo_bibcode, b.otype "
        "FROM basic AS b JOIN ident AS i ON b.oid = i.oidref "
        f"WHERE i.id = '{safe}'"
    )
    for endpoint in (SIMBAD_TAP, "https://simbad.cds.unistra.fr/simbad/tap/sync"):
        try:
            resp = await request_with_retry(
                client,
                "GET",
                endpoint,
                params={"REQUEST": "doQuery", "LANG": "ADQL", "FORMAT": "json", "QUERY": adql},
                max_attempts=1,
            )
            data = resp.json()
            rows = data.get("data", [])
            if rows:
                cols = [c["name"] for c in data["metadata"]]
                return dict(zip(cols, rows[0]))
        except Exception:
            continue
    return None


async def gator_catwise_lookup(client, ra_deg: float, dec_deg: float, radius_arcsec: float = 120.0) -> list[dict]:
    """Query IRSA CatWISE2020 cone around (ra, dec) for high-PM brown dwarfs (W1/W2 + PM)."""
    resp = await request_with_retry(
        client,
        "GET",
        GATOR_URL,
        params={
            "catalog": "catwise_2020",
            "spatial": "cone",
            "objstr": f"{ra_deg:.6f} {dec_deg:.6f}",
            "radius": str(radius_arcsec),
            "outfmt": "1",
            "selcols": "source_name,ra,dec,pmra,pmdec,w1mpro,w2mpro",
        },
    )
    lines = resp.text.splitlines()
    if len(lines) < 5:
        print("GATOR RAW:", resp.text[:400])
    cols: list[str] = []
    out: list[dict] = []
    for line in lines:
        if line.startswith("|") and not cols:
            cols = [c.strip() for c in line.strip("|").split("|")]
            continue
        if not line or line[0] in ("\\", "|"):
            continue
        parts = line.split()
        if cols and len(parts) >= len(cols):
            out.append(dict(zip(cols, parts[: len(cols)])))
    return out


async def main() -> None:
    targets = [
        "Barnard's Star",
        "eps Ind A",
        "eps Ind B",
        "WISE J085510.83-071442.5",
        "RW Aur",
        "R Dra",
    ]
    async with create_async_client(timeout_s=25.0) as client:
        print("=== SIMBAD Lookup (ICRS ep=J2000) ===")
        simbad_hits: dict[str, dict] = {}
        for name in targets:
            try:
                hit = await simbad_lookup(client, name)
                simbad_hits[name] = hit or {}
                print(f"{name:26s} -> {hit}")
            except Exception as exc:
                print(f"{name:26s} -> ERR: {exc}")

        print("\n=== CatWISE2020 Verification for Cold Brown Dwarfs (WISE 0855 & eps Ind B) ===")
        for label, ra0, dec0 in [
            ("WISE 0855 (NASA coords)", 133.795129, -7.245147),
            ("eps Ind B region (SIMBAD)", simbad_hits.get("eps Ind B", {}).get("ra") or 331.065, simbad_hits.get("eps Ind B", {}).get("dec") or -56.79),
        ]:
            try:
                cw = await gator_catwise_lookup(client, float(ra0), float(dec0), 120.0)
                print(f"{label}: {len(cw)} CatWISE sources in 120\"; highest |pm|:")
                ranked = []
                for row in cw:
                    try:
                        pm = math.hypot(float(row["pmra"]), float(row["pmdec"]))
                    except (ValueError, TypeError):
                        pm = -1.0
                    ranked.append((pm, row))
                ranked.sort(key=lambda x: -x[0])
                for pm, row in ranked[:3]:
                    print(f"   pm={pm:.0f} as*1000/yr | {row}")
            except Exception as exc:
                print(f"{label} CatWISE ERR: {exc}")

        print("\n=== Propagated 2025.8 Positions & SPHEREx DR1+QR3 Pass Coverage ===")
        for name in targets:
            hit = simbad_hits.get(name)
            if not hit or hit.get("ra") is None:
                continue
            ra = float(hit["ra"])
            dec = float(hit["dec"])
            pmra = float(hit["pmra"]) if hit.get("pmra") is not None else 0.0
            pmdec = float(hit["pmdec"]) if hit.get("pmdec") is not None else 0.0
            c0 = SkyCoord(
                ra=ra * u.deg,
                dec=dec * u.deg,
                pm_ra_cosdec=pmra * u.mas / u.yr,
                pm_dec=pmdec * u.mas / u.yr,
                obstime=Time(2000.0, format="jyear", scale="tcb"),
                frame="icrs",
            )
            c2026 = c0.apply_space_motion(new_obstime=Time("2026-01-01", scale="utc"))
            sep = c0.separation(c2026).arcsec
            recs = await query_sia(client, float(c2026.ra.deg), float(c2026.dec.deg), ["spherex_dr1", "spherex_qr3"])
            passes, _ = group_passes(recs, gap_days=45.0)
            pass_desc = [(p.label, round(p.mjd_start, 1), round(p.mjd_end, 1), p.n_exposures) for p in passes]
            print(
                f"{name:26s}: J2000=({ra:.6f},{dec:.6f}) -> 2026.0=({c2026.ra.deg:.6f},{c2026.dec.deg:.6f}) "
                f"shift={sep:.1f}\" | {len(recs)} recs, {len(passes)} passes: {pass_desc}"
            )


if __name__ == "__main__":
    asyncio.run(main())
