"""FastAPI integration tests covering targets, manifest/frame serving, and error handlers."""

import json
import numpy as np
from fastapi.testclient import TestClient

from app.config import Settings
from app.io.framepack import decode_framepack, encode_framepack
from app.main import create_app
from app.models import FrameMeta, GridSpec, ProductInfo, SessionManifest, StretchHint, SurveyPass, TargetRef


def test_api_targets_and_synthetic_session_endpoints(tmp_path) -> None:
    preset_dir = tmp_path / "presets"
    cache_dir = tmp_path / "runtime"
    slug_dir = preset_dir / "barnards-star"
    (slug_dir / "frames").mkdir(parents=True)

    blob = encode_framepack(["diff_0"], np.ones((1, 1, 5, 5), dtype=np.float32), np.zeros((1, 5, 5), dtype=np.uint16))
    (slug_dir / "frames" / "diffs.sfp").write_bytes(blob)

    manifest = SessionManifest(
        session_id="barnards-star",
        source="preset",
        target=TargetRef(ra=269.446, dec=4.768, name="Barnard's Star", slug="barnards-star", mjd_ref=61100.0),
        grid=GridSpec(ra0=269.446, dec0=4.768, fov_deg=0.05, npix=5),
        passes=[SurveyPass(index=0, mjd_start=60900.0, mjd_end=60950.0, mjd_mid=60925.0, n_exposures=10, label="Pass 1")],
        products={
            "diffs": ProductInfo(name="diffs", url="/api/sessions/barnards-star/frames/diffs.sfp", n_frames=1, planes_per_frame=1, has_flags=True, bytes=len(blob))
        },
        frames={
            "diffs": [
                FrameMeta(
                    id="diff_0",
                    kind="diff",
                    pass_index=0,
                    pass_label="Pass 1",
                    detector=3,
                    mjd=60925.0,
                    date_utc="2025-09-01 00:00 UTC",
                    wavelength_um=2.0,
                    obs_ids=["o1"],
                    stretch_hint=StretchHint(p_lo=-1.0, p_hi=1.0),
                )
            ]
        },
        created_utc="2026-11-14T01:00:00Z",
        pipeline_version="v1",
    )
    (slug_dir / "manifest.json").write_text(manifest.model_dump_json(), encoding="utf-8")

    cfg = Settings(
        SPX_PRESET_DIR=preset_dir,
        SPX_CACHE_DIR=cache_dir,
        SPX_FRONTEND_DIST=tmp_path / "missing_dist",
    )
    app = create_app(cfg)
    with TestClient(app) as client:
        r_list = client.get("/api/targets")
        assert r_list.status_code == 200
        items = r_list.json()
        assert len(items) == 5
        bs = next(t for t in items if t["slug"] == "barnards-star")
        assert bs["has_preset_bundle"] is True

        r_manifest = client.get("/api/targets/barnards-star")
        assert r_manifest.status_code == 200
        assert r_manifest.json()["session_id"] == "barnards-star"

        r_frame = client.get("/api/sessions/barnards-star/frames/diffs.sfp")
        assert r_frame.status_code == 200
        _, arr, _ = decode_framepack(r_frame.content)
        assert arr.shape == (1, 1, 5, 5)

        r_bad = client.get("/api/targets/nonexistent")
        assert r_bad.status_code == 404
        assert r_bad.json()["error_code"] == "TARGET_NOT_FOUND"

        r_bad_prod = client.get("/api/sessions/barnards-star/frames/unknown.sfp")
        assert r_bad_prod.status_code == 404
        assert r_bad_prod.json()["error_code"] == "BAD_PRODUCT"


def test_api_overlays_thumb_spectrum_and_spa(tmp_path) -> None:
    preset_dir = tmp_path / "presets"
    slug_dir = preset_dir / "barnards-star"
    slug_dir.mkdir(parents=True)
    dist_dir = tmp_path / "dist"
    dist_dir.mkdir(parents=True)
    (dist_dir / "index.html").write_text("<!doctype html><html><body>SPHEREx OK</body></html>", encoding="utf-8")

    (slug_dir / "thumb.webp").write_bytes(b"RIFF\x00\x00\x00\x00WEBP")
    (slug_dir / "spectrum.json").write_text(
        json.dumps(
            {
                "ra": 269.446,
                "dec": 4.768,
                "points": [
                    {
                        "wavelength_um": 4.5,
                        "flux_mjysr": 12.3,
                        "err": 0.1,
                        "detector": 6,
                        "mjd": 61100.0,
                        "obs_id": "obs_1",
                        "flagged": False,
                    }
                ],
                "aperture_arcsec": 9.2,
                "n_used": 1,
                "n_rejected": 0,
            }
        ),
        encoding="utf-8",
    )
    (slug_dir / "overlays.json").write_text(
        json.dumps(
            {
                "gaia": [
                    {
                        "source_id": "g1",
                        "ra": 269.4485,
                        "dec": 4.7394,
                        "g_mag": 8.2,
                        "pmra": -800.0,
                        "pmdec": 10360.0,
                        "ra_at_mjd": 269.4485,
                        "dec_at_mjd": 4.7394,
                    }
                ],
                "allwise": [{"designation": "w1", "ra": 269.448, "dec": 4.74, "w1": 11.0, "w2": 10.9}],
                "source": "preset",
                "mjd_ref": 61000.0,
            }
        ),
        encoding="utf-8",
    )
    manifest = SessionManifest(
        session_id="barnards-star",
        source="preset",
        target=TargetRef(ra=269.446, dec=4.768, name="Barnard's Star", slug="barnards-star", mjd_ref=61000.0),
        grid=GridSpec(ra0=269.446, dec0=4.768, fov_deg=0.05, npix=5),
        passes=[SurveyPass(index=0, mjd_start=60900.0, mjd_end=60950.0, mjd_mid=60925.0, n_exposures=2, label="Pass 1")],
        products={},
        frames={},
        created_utc="2026-11-14T01:00:00Z",
        pipeline_version="v1",
    )
    (slug_dir / "manifest.json").write_text(manifest.model_dump_json(), encoding="utf-8")

    cfg = Settings(
        SPX_PRESET_DIR=preset_dir,
        SPX_CACHE_DIR=tmp_path / "runtime",
        SPX_FRONTEND_DIST=dist_dir,
    )
    with TestClient(create_app(cfg)) as client:
        r_thumb = client.get("/api/targets/barnards-star/thumb.webp")
        assert r_thumb.status_code == 200
        assert "webp" in r_thumb.headers["content-type"]

        r_spec = client.get("/api/sessions/barnards-star/spectrum?ra=269.446&dec=4.768")
        assert r_spec.status_code == 200
        assert r_spec.json()["n_used"] == 1

        r_ov = client.get("/api/overlays?ra=269.446&dec=4.768&fov=0.05&mjd=61365.25&preset=barnards-star")
        assert r_ov.status_code == 200
        ov = r_ov.json()
        assert ov["source"] == "preset"
        # Propagated to MJD 61365.25 (~2026.8): dec shifts noticeably North from 4.7394
        assert ov["gaia"][0]["dec_at_mjd"] > 4.76

        r_spa = client.get("/")
        assert r_spa.status_code == 200
        assert "SPHEREx OK" in r_spa.text

        r_api_404 = client.get("/api/does-not-exist")
        assert r_api_404.status_code == 404
        assert r_api_404.json()["error_code"] == "NOT_FOUND"

        r_bad_sess = client.get("/api/sessions/bad$id/frames/diffs.sfp")
        assert r_bad_sess.status_code == 400
        assert r_bad_sess.json()["error_code"] == "INVALID_SESSION_ID"

        r_bad_dec = client.get("/api/sessions/barnards-star/spectrum?ra=269.4&dec=95.0")
        assert r_bad_dec.status_code == 422

        # Verify live overlay disk cache serves cached overlays offline with dynamic MJD propagation
        live_ov_dir = tmp_path / "runtime" / "overlays"
        live_ov_dir.mkdir(parents=True, exist_ok=True)
        (live_ov_dir / "120.0000_10.0000_0.050.json").write_text(
            json.dumps(
                {
                    "gaia": [
                        {
                            "source_id": "g_live",
                            "ra": 120.0,
                            "dec": 10.0,
                            "g_mag": 12.0,
                            "pmra": 0.0,
                            "pmdec": 3600.0,
                            "ra_at_mjd": 120.0,
                            "dec_at_mjd": 10.0,
                        }
                    ],
                    "allwise": [],
                    "source": "live",
                    "mjd_ref": 61000.0,
                }
            ),
            encoding="utf-8",
        )
        r_cached_ov = client.get("/api/overlays?ra=120.0&dec=10.0&fov=0.05&mjd=61365.25")
        assert r_cached_ov.status_code == 200
        assert r_cached_ov.json()["gaia"][0]["dec_at_mjd"] > 10.0005

        r_health = client.get("/api/health")
        assert r_health.status_code == 200
        h = r_health.json()
        assert h["presets_ready"] == ["barnards-star"]
        assert h["cache_entries"] == 0


def test_api_live_spectrum_lru_cache_and_offcenter(tmp_path) -> None:
    from tests.conftest import gaussian_star, make_test_wcs
    from app.data.cache import DiskCache

    preset_dir = tmp_path / "presets"
    slug_dir = preset_dir / "barnards-star"
    (slug_dir / "frames").mkdir(parents=True)

    wcs = make_test_wcs(200.0, 15.0, npix=25)
    hdr_str = wcs.to_header(relax=True).tostring(sep="\n", endcard=True)
    img = np.full((25, 25), 10.0, dtype=np.float32) + gaussian_star((25, 25), 12.0, 12.0, flux=120.0, sigma=0.8)
    local_raw = DiskCache(slug_dir / "raw_subimages")
    local_raw.put_raw(
        "obs_d5",
        5,
        200.0,
        15.0,
        0.05,
        image=img,
        flags=np.zeros((25, 25), dtype=np.int32),
        variance=np.full((25, 25), 1.0, dtype=np.float32),
        zodi=np.full((25, 25), 4.0, dtype=np.float32),
        wavelength_um=4.2,
        wave_map=np.full((25, 25), 4.2, dtype=np.float32),
        wcs_header=hdr_str,
        meta={"detector": 5, "t_mid_mjd": 61000.0, "obs_id": "obs_d5"},
    )
    (slug_dir / "raw_refs.json").write_text(
        json.dumps([{"obs_id": "obs_d5", "detector": 5, "ra_deg": 200.0, "dec_deg": 15.0, "fov_deg": 0.05}]),
        encoding="utf-8",
    )
    manifest = SessionManifest(
        session_id="barnards-star",
        source="preset",
        target=TargetRef(ra=200.0, dec=15.0, name="Barnard's Star", slug="barnards-star", mjd_ref=61000.0),
        grid=GridSpec(ra0=200.0, dec0=15.0, fov_deg=0.05, npix=25),
        passes=[SurveyPass(index=0, mjd_start=60900.0, mjd_end=60950.0, mjd_mid=60925.0, n_exposures=1, label="Pass 1")],
        products={},
        frames={},
        created_utc="2026-11-14T01:00:00Z",
        pipeline_version="v1",
    )
    (slug_dir / "manifest.json").write_text(manifest.model_dump_json(), encoding="utf-8")

    cfg = Settings(
        SPX_PRESET_DIR=preset_dir,
        SPX_CACHE_DIR=tmp_path / "runtime",
        SPX_FRONTEND_DIST=tmp_path / "no_dist",
    )
    with TestClient(create_app(cfg)) as client:
        r1 = client.get("/api/sessions/barnards-star/spectrum?ra=200.0&dec=15.0")
        assert r1.status_code == 200
        assert r1.json()["n_used"] == 1
        flux1 = r1.json()["points"][0]["flux_mjysr"]
        assert flux1 > 5.0

        # Remove disk cache file to verify second click hits bounded in-memory LRU cache cleanly
        for f in (slug_dir / "raw_subimages").rglob("*.npz"):
            f.unlink()
        r2 = client.get("/api/sessions/barnards-star/spectrum?ra=200.0&dec=15.0")
        assert r2.status_code == 200
        assert r2.json()["points"][0]["flux_mjysr"] == flux1


def test_api_pattern_detection_mover_and_validation(tmp_path) -> None:
    from tests.conftest import gaussian_star

    preset_dir = tmp_path / "presets"
    slug_dir = preset_dir / "mover-synth"
    (slug_dir / "frames").mkdir(parents=True)

    npix = 25
    past = gaussian_star((npix, npix), 12.0, 10.0, flux=60.0, sigma=0.8)
    present = gaussian_star((npix, npix), 12.0, 13.0, flux=60.0, sigma=0.8)
    diff = (present - past).astype(np.float32)

    blob_c = encode_framepack(
        ["c0_d1", "c1_d1"],
        np.stack([past, present], axis=0)[:, np.newaxis, :, :],
        np.zeros((2, npix, npix), dtype=np.uint16),
    )
    blob_d = encode_framepack(
        ["d1_0"],
        diff[np.newaxis, np.newaxis, :, :],
        np.zeros((1, npix, npix), dtype=np.uint16),
    )
    (slug_dir / "frames" / "pass_coadds.sfp").write_bytes(blob_c)
    (slug_dir / "frames" / "diffs.sfp").write_bytes(blob_d)

    manifest = SessionManifest(
        session_id="mover-synth",
        source="live",
        target=TargetRef(ra=180.0, dec=0.0, name="Synth Mover"),
        grid=GridSpec(ra0=180.0, dec0=0.0, fov_deg=0.05, npix=npix),
        passes=[
            SurveyPass(index=0, mjd_start=60800.0, mjd_end=60810.0, mjd_mid=60805.0, n_exposures=1, label="Pass 1"),
            SurveyPass(index=1, mjd_start=61100.0, mjd_end=61110.0, mjd_mid=61105.0, n_exposures=1, label="Pass 2"),
        ],
        products={
            "pass_coadds": ProductInfo(name="pass_coadds", url="/api/sessions/mover-synth/frames/pass_coadds.sfp", n_frames=2, planes_per_frame=1, has_flags=True, bytes=len(blob_c)),
            "diffs": ProductInfo(name="diffs", url="/api/sessions/mover-synth/frames/diffs.sfp", n_frames=1, planes_per_frame=1, has_flags=True, bytes=len(blob_d)),
        },
        frames={
            "pass_coadds": [
                FrameMeta(id="c0_d1", kind="coadd", pass_index=0, pass_label="Pass 1", detector=1, mjd=60805.0, date_utc="2025-05-10", wavelength_um=0.93, obs_ids=["o1"], stretch_hint=StretchHint(p_lo=0.0, p_hi=10.0)),
                FrameMeta(id="c1_d1", kind="coadd", pass_index=1, pass_label="Pass 2", detector=1, mjd=61105.0, date_utc="2026-03-06", wavelength_um=0.93, obs_ids=["o2"], stretch_hint=StretchHint(p_lo=0.0, p_hi=10.0)),
            ],
            "diffs": [
                FrameMeta(id="d1_0", kind="diff", pass_index=1, pass_label="Pass 2 - Pass 1", detector=1, mjd=61105.0, date_utc="2026-03-06", wavelength_um=0.93, obs_ids=["o1", "o2"], stretch_hint=StretchHint(p_lo=-10.0, p_hi=10.0), ref_pass_index=0),
            ],
        },
        created_utc="2026-11-15T00:00:00Z",
        pipeline_version="v1",
    )
    (slug_dir / "manifest.json").write_text(manifest.model_dump_json(), encoding="utf-8")

    cfg = Settings(
        SPX_PRESET_DIR=preset_dir,
        SPX_CACHE_DIR=tmp_path / "runtime",
        SPX_FRONTEND_DIST=tmp_path / "no_dist",
    )
    with TestClient(create_app(cfg)) as client:
        r_pat = client.get("/api/sessions/mover-synth/patterns")
        assert r_pat.status_code == 200
        pat = r_pat.json()
        assert pat["n_patterns"] >= 1
        assert pat["candidates"][0]["kind"] == "mover"
        assert pat["candidates"][0]["metrics"]["direction"] == "N"

        r_bad = client.get("/api/sessions/bad$id/patterns")
        assert r_bad.status_code == 400
        assert r_bad.json()["error_code"] == "INVALID_SESSION_ID"
