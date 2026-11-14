"""Network integration test verifying live range-read parity with IRSA cutout service."""

import numpy as np
import pytest

from app.data.http import create_async_client
from app.data.reader import read_cutout, read_range
from app.data.sia import query as query_sia


@pytest.mark.network
async def test_range_read_matches_irsa_cutout_pixels_and_wavelength() -> None:
    ra_deg, dec_deg, fov_deg = 269.44623, 4.76881, 0.05
    async with create_async_client(timeout_s=45.0) as client:
        recs = await query_sia(client, ra_deg, dec_deg, ["spherex_dr1"])
        d6_recs = [r for r in recs if r.detector == 6]
        rec = d6_recs[0] if d6_recs else recs[0]

        sub_rng = await read_range(client, rec, ra_deg, dec_deg, fov_deg)
        sub_cut = await read_cutout(client, rec, ra_deg, dec_deg, fov_deg)

        cy, cx = sub_cut["image"].shape[0] // 2, sub_cut["image"].shape[1] // 2
        r_c, d_c = sub_cut["wcs"].pixel_to_world_values(cx, cy)
        rx, ry = sub_rng["wcs"].world_to_pixel_values(float(r_c), float(d_c))
        ix, iy = int(round(float(rx))), int(round(float(ry)))

        val_cut = float(sub_cut["image"][cy, cx])
        val_rng = float(sub_rng["image"][iy, ix])
        if np.isfinite(val_cut):
            assert abs(val_cut - val_rng) < 1e-4
        assert abs(float(sub_cut["wave_map"][cy, cx]) - float(sub_rng["wave_map"][iy, ix])) < 1e-4
