"""Verify integrity, dimensions, dtypes, bitmask flags, and SFP1 readability of all pre-warmed Earth presets."""

import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
from PIL import Image

from app.config import get_settings
from app.io.framepack import decode_framepack
from app.models import OverlaySet, SessionManifest, SpectrumResult


FLAGSHIP_PRESETS = [
    "kandy-floods",
    "amazon-drought-fire",
    "mahaweli-rice",
    "jakobshavn-glacier",
    "maui-wildfire",
]

REQUIRED_PRODUCTS = [
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

REQUIRED_SIGNALS = [
    "radar",
    "rain",
    "wind",
    "temp",
    "optical",
    "nightlights",
]


def verify_preset(preset_dir: Path, slug: str) -> dict:
    """Validate completeness, shapes, dtypes, and flags for a single preset."""
    if not preset_dir.is_dir():
        raise FileNotFoundError(f"Preset directory missing: {preset_dir}")

    # 1. Manifest
    manifest_path = preset_dir / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"Missing manifest.json in {preset_dir}")
    man = SessionManifest.model_validate_json(manifest_path.read_text(encoding="utf-8"))
    assert man.session_id == slug, f"Session ID mismatch: {man.session_id} != {slug}"
    assert man.grid.npix == 64, f"Grid npix {man.grid.npix} != 64"
    assert len(man.story_scenes) == 5, f"Expected 5 story scenes, found {len(man.story_scenes)}"
    assert len(man.passes) == 12, f"Expected 12 passes, found {len(man.passes)}"
    for prod in REQUIRED_PRODUCTS:
        assert prod in man.products, f"Product '{prod}' missing in manifest.products"

    # 2. Spectrum Result
    spectrum_path = preset_dir / "spectrum.json"
    if not spectrum_path.exists():
        raise FileNotFoundError(f"Missing spectrum.json in {preset_dir}")
    spec = SpectrumResult.model_validate_json(spectrum_path.read_text(encoding="utf-8"))
    assert len(spec.series) == 6, f"Expected 6 signal series, found {len(spec.series)}"
    for sig in REQUIRED_SIGNALS:
        assert sig in spec.series, f"Signal '{sig}' missing from spectrum.json series"
        assert len(spec.series[sig]) == 12, f"Signal '{sig}' series length {len(spec.series[sig])} != 12"
    assert len(spec.dates) == 12, f"Expected 12 dates in spectrum.json, found {len(spec.dates)}"

    # 3. Overlays
    overlays_path = preset_dir / "overlays.json"
    if not overlays_path.exists():
        raise FileNotFoundError(f"Missing overlays.json in {preset_dir}")
    ov = OverlaySet.model_validate_json(overlays_path.read_text(encoding="utf-8"))

    # 4. Thumbnail
    thumb_path = preset_dir / "thumb.webp"
    if not thumb_path.exists():
        raise FileNotFoundError(f"Missing thumb.webp in {preset_dir}")
    assert thumb_path.stat().st_size > 100, f"Thumbnail {thumb_path} is suspiciously small ({thumb_path.stat().st_size} bytes)"
    with Image.open(thumb_path) as im:
        assert im.format == "WEBP", f"Thumbnail format {im.format} != WEBP"
        assert im.size == (160, 160), f"Thumbnail size {im.size} != (160, 160)"

    # 5. SFP1 Frames
    frames_dir = preset_dir / "frames"
    if not frames_dir.is_dir():
        raise FileNotFoundError(f"Missing frames directory in {preset_dir}")

    shapes: dict[str, tuple[int, ...]] = {}
    for prod in REQUIRED_PRODUCTS:
        sfp_path = frames_dir / f"{prod}.sfp"
        if not sfp_path.exists():
            raise FileNotFoundError(f"Missing framepack: {sfp_path}")
        raw_bytes = sfp_path.read_bytes()
        header, data, flags = decode_framepack(raw_bytes)

        assert header["n_frames"] == 12, f"{prod} n_frames != 12"
        assert header["npix"] == 64, f"{prod} npix != 64"
        assert header["dtype"] == "float32", f"{prod} dtype != float32"
        assert data.dtype == np.float32, f"{prod} data.dtype {data.dtype} != float32"

        if prod == "rgb":
            assert data.shape == (12, 3, 64, 64), f"RGB shape {data.shape} != (12, 3, 64, 64)"
        else:
            assert data.shape == (12, 1, 64, 64), f"{prod} shape {data.shape} != (12, 1, 64, 64)"

        assert flags is not None, f"{prod} uint16 flags missing"
        assert flags.dtype == np.uint16, f"{prod} flags.dtype {flags.dtype} != uint16"
        assert flags.shape == (12, 64, 64), f"{prod} flags.shape {flags.shape} != (12, 64, 64)"

        shapes[prod] = tuple(data.shape)

    total_bytes = sum(f.stat().st_size for f in preset_dir.rglob("*") if f.is_file())
    return {
        "slug": slug,
        "name": man.target.name,
        "category": man.category,
        "scenes": len(man.story_scenes),
        "products": len(shapes),
        "bytes": total_bytes,
        "shapes": shapes,
    }


def main() -> None:
    settings = get_settings()
    root = settings.spx_preset_dir
    print(f"Verifying pre-baked Earth presets in: {root}")

    if not root.is_dir():
        print(f"ERROR: Preset directory '{root}' does not exist.")
        sys.exit(1)

    total_all_bytes = 0
    verified_count = 0

    for slug in FLAGSHIP_PRESETS:
        preset_dir = root / slug
        info = verify_preset(preset_dir, slug)
        total_all_bytes += info["bytes"]
        verified_count += 1
        print(
            f"  [PASS] {slug:<22} | Category: {info['category']:<18} | "
            f"Scenes: {info['scenes']} | Products: {info['products']}/10 SFP1 | "
            f"Size: {info['bytes'] / 1e6:.2f} MB"
        )

    # Verify index.json
    index_path = root / "index.json"
    if not index_path.exists():
        raise FileNotFoundError(f"Missing index.json in {root}")
    index_data = json.loads(index_path.read_text(encoding="utf-8"))
    assert len(index_data) == 5, f"index.json has {len(index_data)} entries, expected 5"
    index_slugs = {item["slug"] for item in index_data}
    assert index_slugs == set(FLAGSHIP_PRESETS), f"index.json slugs mismatch: {index_slugs}"
    print(f"  [PASS] index.json verified with all 5 flagship presets.")

    print(f"\nSUCCESS: All {verified_count}/5 flagship Earth presets verified ({total_all_bytes / 1e6:.2f} MB total).")


if __name__ == "__main__":
    main()
