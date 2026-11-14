"""Phase 0 benchmark: measure read_range vs read_cutout latency and verify pixel + WCS-WAVE parity."""

import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
from app.data.http import create_async_client
from app.data.reader import read_cutout, read_range
from app.data.sia import query as query_sia


async def main() -> None:
    ra_deg, dec_deg, fov_deg = 269.44623, 4.76881, 0.05  # Barnard's Star @2026
    async with create_async_client(timeout_s=45.0) as client:
        recs = await query_sia(client, ra_deg, dec_deg, ["spherex_dr1"])
        sample = recs[:2]
        for rec in sample:
            print(f"\n--- Benchmarking {rec.obs_id} D{rec.detector} ({rec.access_url.split('/')[-1]}) ---")
            t0 = time.perf_counter()
            sub_rng = await read_range(client, rec, ra_deg, dec_deg, fov_deg)
            dt_rng = time.perf_counter() - t0
            print(f"  read_range : {dt_rng:.2f}s | shape={sub_rng['image'].shape} | lam_med={sub_rng['wavelength_um']:.4f} um")

            t1 = time.perf_counter()
            sub_cut = await read_cutout(client, rec, ra_deg, dec_deg, fov_deg)
            dt_cut = time.perf_counter() - t1
            print(f"  read_cutout: {dt_cut:.2f}s | shape={sub_cut['image'].shape} | lam_med={sub_cut['wavelength_um']:.4f} um")

            # Verify pixel-exact match at overlapping sky location (center pixel of cutout in range slice)
            r_c, d_c = sub_cut["wcs"].pixel_to_world_values(
                sub_cut["image"].shape[1] // 2,
                sub_cut["image"].shape[0] // 2,
            )
            rx, ry = sub_rng["wcs"].world_to_pixel_values(float(r_c), float(d_c))
            cx, cy = sub_cut["image"].shape[1] // 2, sub_cut["image"].shape[0] // 2
            ix, iy = int(round(float(rx))), int(round(float(ry)))
            val_cut = float(sub_cut["image"][cy, cx])
            val_rng = float(sub_rng["image"][iy, ix])
            wav_cut = float(sub_cut["wave_map"][cy, cx])
            wav_rng = float(sub_rng["wave_map"][iy, ix])
            diff = abs(val_cut - val_rng)
            wdiff = abs(wav_cut - wav_rng)
            print(f"  Pixel check  : cut={val_cut:.5f}, rng={val_rng:.5f}, abs_diff={diff:.2e}")
            print(f"  Wave  check  : cut={wav_cut:.5f} um, rng={wav_rng:.5f} um, diff={wdiff:.2e}")
            print(f"  Speedup      : {dt_cut / max(dt_rng, 0.01):.2f}x")


if __name__ == "__main__":
    asyncio.run(main())
