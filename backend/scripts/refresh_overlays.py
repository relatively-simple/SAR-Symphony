"""Refresh Gaia DR3 + AllWISE overlays.json and target spectrum.json across ready presets."""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import get_settings
from app.core.coords import mid_epoch
from app.data.cache import DiskCache
from app.data.catalogs import query_live_overlays
from app.data.http import create_async_client
from app.pipeline.session import list_ready_presets, load_manifest
from app.science.spectrum import extract_spectrum_at


async def main() -> None:
    settings = get_settings()
    slugs = list_ready_presets(settings.spx_preset_dir)
    async with create_async_client(timeout_s=25.0) as client:
        for slug in slugs:
            sdir = settings.spx_preset_dir / slug
            manifest = load_manifest(settings, slug)
            mjd_ref = manifest.target.mjd_ref or mid_epoch(manifest.passes)

            # Recompute spectrum.json quickly from local bundled raw_subimages
            spec_n = 0
            refs_path = sdir / "raw_refs.json"
            raw_dir = sdir / "raw_subimages"
            if refs_path.exists() and raw_dir.exists():
                refs = json.loads(refs_path.read_text(encoding="utf-8"))
                lc = DiskCache(raw_dir)
                subs = [
                    s
                    for s in (
                        lc.get_raw(r["obs_id"], r["detector"], r["ra_deg"], r["dec_deg"], r["fov_deg"])
                        for r in refs
                    )
                    if s is not None
                ]
                spec = extract_spectrum_at(manifest.target.ra, manifest.target.dec, subs)
                (sdir / "spectrum.json").write_text(spec.model_dump_json(indent=2), encoding="utf-8")
                spec_n = spec.n_used

            ov = await query_live_overlays(
                client,
                manifest.target.ra,
                manifest.target.dec,
                manifest.grid.fov_deg,
                mjd_ref,
            )
            ov.source = "preset" if (ov.gaia or ov.allwise) else "unavailable"
            (sdir / "overlays.json").write_text(ov.model_dump_json(indent=2), encoding="utf-8")
            print(
                f"[{slug}] spectrum_pts={spec_n}, gaia={len(ov.gaia)}, allwise={len(ov.allwise)}, note={ov.note}"
            )


if __name__ == "__main__":
    asyncio.run(main())
