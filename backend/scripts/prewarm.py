"""Pre-warm offline preset bundles for all 5 official NASA Space Apps Challenge 2026 Earth presets."""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
from PIL import Image

from app.config import get_settings
from app.core.presets import FLAGSHIP_PRESETS, PRESETS
from app.io.framepack import encode_framepack
from app.models import (
    OverlaySet,
    ProductInfo,
    SessionManifest,
    TargetRef,
)
from app.pipeline.session import DEFAULT_CITATIONS
from app.science.earth_signals import extract_signal_rhythm_at, generate_multi_sensor_cube


ALL_10_PRODUCTS = [
    "radar",
    "rain",
    "wind",
    "temp",
    "optical",
    "nightlights",
    "pass_coadds",
    "diffs",
    "rgb",
    "coldglow",
]


def _render_thumbnail(preset_dir: Path, slug: str, compiled_products: dict) -> None:
    """Render a crisp 160x160 preview WebP thumbnail representing the Earth event."""
    rgb_prod = compiled_products.get("rgb")
    if rgb_prod is not None:
        # Use peak frame (index 6) from RGB composite
        rgb_data = rgb_prod.data[6]  # (3, 64, 64)
        rgb_t = np.transpose(rgb_data, (1, 2, 0))  # (64, 64, 3)
        img_u8 = (np.clip(rgb_t, 0.0, 1.0) * 255.0).astype(np.uint8)
    else:
        # Fallback to radar backscatter normalization
        radar_prod = compiled_products["radar"]
        r_slice = radar_prod.data[6, 0]  # (64, 64)
        norm = np.clip((r_slice + 25.0) / 25.0, 0.0, 1.0)
        val = (norm * 255.0).astype(np.uint8)
        img_u8 = np.stack([val, val, val], axis=-1)

    # Flip vertically so North (+Y) renders up in standard screen coordinates
    img_u8 = np.flipud(img_u8)
    pil = Image.fromarray(img_u8, mode="RGB").resize((160, 160), Image.Resampling.LANCZOS)
    pil.save(preset_dir / "thumb.webp", format="WEBP", quality=90)


def build_preset(slug: str) -> dict:
    """Compile and verify one preset bundle cleanly into cache/presets/<slug>/."""
    settings = get_settings()
    preset = PRESETS[slug]
    out_dir = settings.spx_preset_dir / slug
    frames_dir = out_dir / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)

    lon = float(preset.lon if preset.lon is not None else preset.ra_deg)
    lat = float(preset.lat if preset.lat is not None else preset.dec_deg)
    fov = float(preset.default_fov)

    print(f"  [{slug}] Generating 64x64 multi-sensor cube (lon={lon:.4f}, lat={lat:.4f}, fov={fov}°)...")
    compiled_products, passes, grid_spec = generate_multi_sensor_cube(
        lon=lon,
        lat=lat,
        fov_deg=fov,
        preset_slug=slug,
        npix=64,
        n_frames=12,
    )

    prod_infos: dict[str, ProductInfo] = {}
    frames_meta: dict[str, list] = {}

    for name in ALL_10_PRODUCTS:
        prod = compiled_products[name]
        blob = encode_framepack(prod.frame_ids, prod.data, prod.flags)
        sfp_path = frames_dir / f"{name}.sfp"
        sfp_path.write_bytes(blob)
        prod_infos[name] = ProductInfo(
            name=name,
            url=f"/api/sessions/{slug}/frames/{name}.sfp",
            n_frames=len(prod.frame_ids),
            planes_per_frame=prod.planes_per_frame,
            has_flags=prod.flags is not None,
            bytes=len(blob),
        )
        frames_meta[name] = prod.metas

    manifest = SessionManifest(
        session_id=slug,
        source="preset",
        target=TargetRef(
            ra=round(lon, 6),
            dec=round(lat, 6),
            lon=round(lon, 6),
            lat=round(lat, 6),
            name=preset.name,
            slug=slug,
            mjd_ref=passes[0].mjd_mid if passes else 60997.0,
        ),
        grid=grid_spec,
        passes=passes,
        products=prod_infos,
        frames=frames_meta,
        warnings=[preset.caveat] if preset.caveat else [],
        citations=DEFAULT_CITATIONS,
        created_utc=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        pipeline_version="v2.1-earth-symphony",
        category=preset.category,
        region_label=preset.region_label,
        sensors_used=preset.sensors_used,
        story_scenes=preset.story_scenes,
        geo_features=preset.geo_features,
        causal_summary=preset.causal_summary,
        event_dates=preset.event_dates,
        illusion_summary=preset.illusion_summary,
    )
    (out_dir / "manifest.json").write_text(manifest.model_dump_json(indent=2), encoding="utf-8")

    # Precompute center 6-signal spectrum timeline
    spec = extract_signal_rhythm_at(lon=lon, lat=lat, session_dir=out_dir, manifest=manifest)
    (out_dir / "spectrum.json").write_text(spec.model_dump_json(indent=2), encoding="utf-8")

    # Write preset overlays
    overlays = OverlaySet(
        gaia=[],
        allwise=[],
        source="preset",
        mjd_ref=2026.0,
        note=f"Earth surface preset: {preset.name}",
    )
    (out_dir / "overlays.json").write_text(overlays.model_dump_json(indent=2), encoding="utf-8")

    # Write thumbnail
    _render_thumbnail(out_dir, slug, compiled_products)

    total_bytes = sum(f.stat().st_size for f in out_dir.rglob("*") if f.is_file())
    print(
        f"  [{slug}] DONE: 10 SFP1 products, passes={len(manifest.passes)}, "
        f"story_scenes={len(manifest.story_scenes)}, size={total_bytes / 1e6:.2f} MB"
    )

    return {
        "slug": slug,
        "name": preset.name,
        "title": preset.title or preset.name,
        "category": preset.category,
        "region_label": preset.region_label,
        "lon": lon,
        "lat": lat,
        "passes": len(manifest.passes),
        "products": list(prod_infos.keys()),
        "sensors_used": preset.sensors_used,
        "story_scenes_count": len(preset.story_scenes),
        "bytes": total_bytes,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Prewarm SAR Symphony Earth event preset bundles.")
    parser.add_argument("--targets", nargs="*", default=list(FLAGSHIP_PRESETS))
    args = parser.parse_args()

    settings = get_settings()
    settings.spx_preset_dir.mkdir(parents=True, exist_ok=True)

    summary = []
    for slug in args.targets:
        if slug not in PRESETS:
            raise SystemExit(f"Unknown preset '{slug}'")
        info = build_preset(slug)
        summary.append(info)

    index_path = settings.spx_preset_dir / "index.json"
    index_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"\nSuccessfully wrote {index_path} ({len(summary)} presets tracked).")


if __name__ == "__main__":
    main()
