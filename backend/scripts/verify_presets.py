"""Verify integrity, dimensions, sizes, and SFP1 readability of all pre-warmed presets."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import get_settings
from app.io.framepack import decode_framepack


def main() -> None:
    settings = get_settings()
    root = settings.spx_preset_dir
    total_all = 0
    for d in sorted(root.iterdir()):
        if not d.is_dir():
            continue
        m = d / "manifest.json"
        if not m.exists():
            print(f"{d.name}: INCOMPLETE")
            continue
        man = json.loads(m.read_text(encoding="utf-8"))
        ov = json.loads((d / "overlays.json").read_text(encoding="utf-8")) if (d / "overlays.json").exists() else {}
        sp = json.loads((d / "spectrum.json").read_text(encoding="utf-8")) if (d / "spectrum.json").exists() else {}
        bytes_cnt = sum(f.stat().st_size for f in d.rglob("*") if f.is_file())
        total_all += bytes_cnt
        shapes = {}
        for pname in man["products"]:
            raw = (d / "frames" / f"{pname}.sfp").read_bytes()
            _, arr, _ = decode_framepack(raw)
            shapes[pname] = tuple(arr.shape)
        print(
            f"{d.name}: passes={len(man['passes'])}, npix={man['grid']['npix']}, "
            f"spec_pts={sp.get('n_used', 0)}, gaia={len(ov.get('gaia', []))}, "
            f"wise={len(ov.get('allwise', []))}, size={bytes_cnt / 1e6:.2f} MB, shapes={shapes}"
        )
    print(f"Total preset bundle size: {total_all / 1e6:.2f} MB")


if __name__ == "__main__":
    main()
