"""IRSA SIAv2 discovery client for SPHEREx DR1 and QR3 spectral images."""

import asyncio
import xml.etree.ElementTree as ET
import httpx

from app.core.detectors import bandpass_to_detector
from app.core.errors import ExploreError
from app.data.http import request_with_retry
from app.models import ExposureRecord


IRSA_SIA_ENDPOINT = "https://irsa.ipac.caltech.edu/SIA"


def parse_votable(xml_bytes: bytes, collection: str) -> list[ExposureRecord]:
    """Parse an IVOA SIAv2 VOTable XML response into normalized ExposureRecord items."""
    root = ET.fromstring(xml_bytes)
    ns = {"v": root.tag.split("}")[0].strip("{")} if "}" in root.tag else {}
    fields_el = root.findall(".//v:FIELD", ns) or root.findall(".//FIELD")
    rows_el = root.findall(".//v:TR", ns) or root.findall(".//TR")
    field_names = [f.attrib.get("name", "") for f in fields_el]

    records: list[ExposureRecord] = []
    for tr in rows_el:
        values = [td.text or "" for td in tr]
        row = dict(zip(field_names, values))

        access_url = row.get("access_url", "").strip()
        obs_id = row.get("obs_id", "").strip()
        detector = bandpass_to_detector(row.get("energy_bandpassname"))
        if not access_url or not obs_id or detector is None:
            continue

        try:
            t_min = float(row["t_min"])
            t_max = float(row.get("t_max") or t_min)
            em_min_um = float(row.get("em_min") or 0.0) * 1e6
            em_max_um = float(row.get("em_max") or 0.0) * 1e6
        except (KeyError, ValueError):
            continue

        records.append(
            ExposureRecord(
                obs_id=obs_id,
                collection=collection,
                detector=detector,
                t_mid_mjd=0.5 * (t_min + t_max),
                em_min_um=em_min_um,
                em_max_um=em_max_um,
                access_url=access_url,
            )
        )
    return records


async def query_collection(
    client: httpx.AsyncClient,
    ra_deg: float,
    dec_deg: float,
    collection: str,
    radius_deg: float = 0.015,
) -> list[ExposureRecord]:
    """Query a single SPHEREx IRSA SIAv2 collection around (ra_deg, dec_deg)."""
    pos_str = f"circle {ra_deg:.6f} {dec_deg:.6f} {radius_deg:.4f}"
    resp = await request_with_retry(
        client,
        "GET",
        IRSA_SIA_ENDPOINT,
        params={"COLLECTION": collection, "POS": pos_str},
    )
    return parse_votable(resp.content, collection=collection)


async def query(
    client: httpx.AsyncClient,
    ra_deg: float,
    dec_deg: float,
    collections: list[str],
    radius_deg: float = 0.015,
) -> list[ExposureRecord]:
    """Query all configured collections in parallel, deduplicating preferring earlier list items."""
    tasks = [query_collection(client, ra_deg, dec_deg, col, radius_deg) for col in collections]
    try:
        results = await asyncio.gather(*tasks, return_exceptions=True)
    except Exception as exc:
        raise ExploreError("IRSA_TIMEOUT", f"IRSA SIA query failed: {exc}", 502) from exc

    merged: dict[tuple[str, int], ExposureRecord] = {}
    errors: list[str] = []
    for col, res in zip(collections, results):
        if isinstance(res, Exception):
            errors.append(f"{col}: {res}")
            continue
        for rec in res:
            key = (rec.obs_id, rec.detector)
            # Earlier collections in config (e.g. spherex_dr1 before spherex_qr3) take precedence
            if key not in merged:
                merged[key] = rec

    if not merged:
        if errors and len(errors) == len(collections):
            raise ExploreError(
                "IRSA_TIMEOUT",
                "IRSA SPHEREx search service timed out or could not be reached. Please try again shortly.",
                504,
            )
        raise ExploreError(
            "NO_COVERAGE",
            f"SPHEREx DR1/QR3 has not released exposures covering RA {ra_deg:.4f}°, Dec {dec_deg:.4f}° yet.",
            404,
        )

    ordered = sorted(merged.values(), key=lambda r: (r.t_mid_mjd, r.detector, r.obs_id))
    return ordered
