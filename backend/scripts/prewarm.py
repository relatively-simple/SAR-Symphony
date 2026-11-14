"""Pre-warm offline preset bundles for all 5 official NASA Challenge 12 targets."""

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
from PIL import Image

from app.config import get_settings
from app.core.coords import mid_epoch, propagate
from app.core.presets import PRESETS
from app.data.cache import DiskCache
from app.data.catalogs import query_live_overlays
from app.data.http import create_async_client
from app.io.framepack import decode_framepack
from app.pipeline.run import run_explore_pipeline
from app.pipeline.session import load_manifest
from app.science.spectrum import extract_spectrum_at


def _render_thumbnail(preset_dir: Path, manifest) -> None:
    """Render a crisp 160x160 preview WebP thumbnail matching the preset default_lens."""
    pref = {"motion": "diffs", "coldglow": "coldglow", "variable": "pass_coadds", "rgb": "rgb"}.get(
        manifest.target and PRESETS[manifest.target.slug].default_lens, "pass_coadds"
    )
    prod_name = pref if pref in manifest.products else next(iter(manifest.products))
    sfp_path = preset_dir / "frames" / f"{prod_name}.sfp"
    _, data, _ = decode_framepack(sfp_path.read_bytes())

    metas = manifest.frames[prod_name]
    idx = len(metas) - 1  # Latest pass or Pass N - Pass 1 diff highlights signal best
    hint = metas[idx].stretch_hint

    if data.shape[1] == 3:
        rgb = np.clip(np.transpose(data[idx], (1, 2, 0)), 0.0, 1.0)
        img_u8 = (np.nan_to_num(rgb, nan=0.0) * 255).astype(np.uint8)
    elif prod_name == "diffs":
        arr = data[idx, 0]
        scale = max(abs(hint.p_lo), abs(hint.p_hi), 1e-6)
        v = np.clip(np.nan_to_num(arr, nan=0.0) / scale, -1.0, 1.0)
        r = np.where(v >= 0, 20 + 235 * np.sqrt(np.maximum(v, 0.0)), 20 * (1 + v))
        g = np.where(v >= 0, 22 + 50 * v, 22 + 210 * np.sqrt(np.maximum(-v, 0.0)))
        b = np.where(v >= 0, 34 * (1 - v), 34 + 221 * np.sqrt(np.maximum(-v, 0.0)))
        img_u8 = np.stack([r, g, b], axis=-1).clip(0, 255).astype(np.uint8)
    else:
        arr = np.nan_to_num(data[idx, 0], nan=hint.p_lo)
        norm = np.clip((arr - hint.p_lo) / max(hint.p_hi - hint.p_lo, 1e-6), 0.0, 1.0)
        a = np.arcsinh(norm * 8.0) / np.arcsinh(8.0)
        if prod_name == "coldglow":
            # Dark obsidian -> warm orange/amber glow
            r = (15 + 240 * np.power(a, 0.75)).clip(0, 255)
            g = (12 + 190 * np.power(a, 1.3)).clip(0, 255)
            b = (28 + 140 * np.power(a, 2.1)).clip(0, 255)
            img_u8 = np.stack([r, g, b], axis=-1).astype(np.uint8)
        else:
            val = (a * 255).astype(np.uint8)
            img_u8 = np.stack([val, val, val], axis=-1)

    # Flip vertically so North (+Y) renders up in standard PNG/WebP screen coordinates
    img_u8 = np.flipud(img_u8)
    pil = Image.fromarray(img_u8, mode="RGB").resize((160, 160), Image.Resampling.BILINEAR)
    pil.save(preset_dir / "thumb.webp", format="WEBP", quality=88)


async def build_preset(slug: str, per_pass_det: int = 6) -> dict:
    """Compile and verify one preset bundle cleanly into cache/presets/<slug>/."""
    settings = get_settings()
    preset = PRESETS[slug]
    out_dir = settings.spx_preset_dir / slug
    out_dir.mkdir(parents=True, exist_ok=True)

    # Initial ~2026 center seed (refined automatically by mid_epoch inside run_explore_pipeline)
    c_seed = propagate(preset, 61050.0)
    last_ev = None
    async for ev in run_explore_pipeline(
        f"{c_seed.ra.deg:.6f}",
        f"{c_seed.dec.deg:.6f}",
        preset.default_fov,
        settings,
        preset_slug=slug,
        per_pass_det_override=per_pass_det,
        output_dir_override=out_dir,
        source_kind="preset",
    ):
        print(f"  [{slug}] {ev.stage}: {ev.message}")
        last_ev = ev

    if not last_ev or last_ev.stage != "done":
        raise RuntimeError(f"Failed prewarming {slug}: {last_ev}")

    manifest = load_manifest(settings, slug)

    # Copy exact raw subimages locally inside preset so arbitrary pixel spectra work offline
    runtime_cache = DiskCache(settings.spx_cache_dir)
    preset_raw_cache = DiskCache(out_dir / "raw_subimages")
    refs = json.loads((out_dir / "raw_refs.json").read_text(encoding="utf-8"))
    subimages = []
    for ref in refs:
        sub = runtime_cache.get_raw(
            ref["obs_id"], ref["detector"], ref["ra_deg"], ref["dec_deg"], ref["fov_deg"]
        )
        if sub is not None:
            subimages.append(sub)
            preset_raw_cache.put_raw(
                ref["obs_id"],
                ref["detector"],
                ref["ra_deg"],
                ref["dec_deg"],
                ref["fov_deg"],
                image=sub["image"],
                flags=sub["flags"],
                variance=sub["variance"],
                zodi=sub["zodi"],
                wavelength_um=sub["wavelength_um"],
                wave_map=sub["wave_map"],
                wcs_header=sub["wcs_header"],
                meta=sub["meta"],
            )

    # Precompute center spectrum JSON
    spec = extract_spectrum_at(manifest.target.ra, manifest.target.dec, subimages)
    (out_dir / "spectrum.json").write_text(spec.model_dump_json(indent=2), encoding="utf-8")

    # Fetch cross-mission Gaia DR3 + AllWISE overlays for preset
    async with create_async_client(timeout_s=20.0) as client:
        overlays = await query_live_overlays(
            client,
            manifest.target.ra,
            manifest.target.dec,
            manifest.grid.fov_deg,
            manifest.target.mjd_ref or mid_epoch(manifest.passes),
        )
        overlays.source = "preset" if (overlays.gaia or overlays.allwise) else "unavailable"
        (out_dir / "overlays.json").write_text(overlays.model_dump_json(indent=2), encoding="utf-8")

    _render_thumbnail(out_dir, manifest)

    total_bytes = sum(f.stat().st_size for f in out_dir.rglob("*") if f.is_file())
    print(
        f"  [{slug}] DONE: passes={len(manifest.passes)}, spectrum_pts={spec.n_used}, "
        f"gaia={len(overlays.gaia)}, allwise={len(overlays.allwise)}, size={total_bytes / 1e6:.2f} MB"
    )
    return {
        "slug": slug,
        "name": preset.name,
        "passes": len(manifest.passes),
        "spectrum_pts": spec.n_used,
        "gaia": len(overlays.gaia),
        "allwise": len(overlays.allwise),
        "bytes": total_bytes,
    }


async def main() -> None:
    parser = argparse.ArgumentParser(description="Prewarm SPHEREx preset bundles.")
    parser.add_argument("--targets", nargs="*", default=list(PRESETS.keys()))
    parser.add_argument("--per-pass-det", type=int, default=6)
    args = parser.parse_args()

    settings = get_settings()
    summary = []
    for slug in args.targets:
        if slug not in PRESETS:
            raise SystemExit(f"Unknown preset '{slug}'")
        info = await build_preset(slug, per_pass_det=args.per_pass_det)
        summary.append(info)

    settings.spx_preset_dir.mkdir(parents=True, exist_ok=True)
    index_path = settings.spx_preset_dir / "index.json"
    existing = {}
    if index_path.exists():
        try:
            for item in json.loads(index_path.read_text(encoding="utf-8")):
                existing[item["slug"]] = item
        except Exception:
            pass
    for item in summary:
        existing[item["slug"]] = item
    index_path.write_text(json.dumps(list(existing.values()), indent=2), encoding="utf-8")
    print(f"\nUpdated {index_path} ({len(existing)} presets tracked).")


if __name__ == "__main__":
    asyncio.run(main())
