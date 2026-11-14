"""End-to-end streaming exploration orchestrator turning sky coordinates into SFP1 bundles."""

import asyncio
import json
from collections.abc import AsyncIterator
from datetime import datetime, timezone
from pathlib import Path
from astropy.coordinates import SkyCoord

from app.config import Settings
from app.core.coords import make_grid, mid_epoch, parse_coords, propagate, validate_fov
from app.core.errors import ExploreError
from app.core.presets import PRESETS
from app.data.cache import DiskCache
from app.data.catalogs import query_live_overlays
from app.data.http import create_async_client
from app.data.planner import group_passes, select
from app.data.reader import read_subimage
from app.data.sia import query as query_sia
from app.io.framepack import encode_framepack
from app.models import ProductInfo, ProgressEvent, SessionManifest, TargetRef
from app.pipeline.session import DEFAULT_CITATIONS, load_manifest, make_session_id, save_manifest
from app.science.align import align_frame
from app.science.clean import clean_subimage
from app.science.products import build_all_products


_SESSION_LOCKS: dict[str, asyncio.Lock] = {}


def _get_session_lock(key: str) -> asyncio.Lock:
    lock = _SESSION_LOCKS.get(key)
    if lock is None:
        if len(_SESSION_LOCKS) > 128:
            # Drop unheld locks cleanly to keep memory bounded
            idle = [k for k, v in _SESSION_LOCKS.items() if not v.locked()]
            for k in idle[:64]:
                _SESSION_LOCKS.pop(k, None)
        lock = asyncio.Lock()
        _SESSION_LOCKS[key] = lock
    return lock


async def run_explore_pipeline(
    ra_str: str,
    dec_str: str,
    fov_deg: float,
    settings: Settings,
    *,
    preset_slug: str | None = None,
    per_pass_det_override: int | None = None,
    output_dir_override: Path | None = None,
    source_kind: str = "live",
) -> AsyncIterator[ProgressEvent]:
    """Run SPHEREx explore pipeline yielding structured ProgressEvent updates cleanly."""
    try:
        fov = validate_fov(fov_deg)
        preset = PRESETS.get(preset_slug) if preset_slug else None
        center = parse_coords(ra_str, dec_str)
    except ExploreError as exc:
        yield ProgressEvent(stage="error", message=exc.message, error_code=exc.error_code)
        return

    yield ProgressEvent(
        stage="resolve",
        message=f"Target centered near RA {center.ra.deg:.4f}°, Dec {center.dec.deg:+.4f}°.",
    )

    # Check if already compiled in presets or runtime sessions
    if output_dir_override is None and preset is not None and abs(fov - preset.default_fov) < 1e-4:
        pdir = settings.spx_preset_dir / preset.slug
        if (pdir / "manifest.json").exists():
            yield ProgressEvent(
                stage="done",
                message=f"Loaded pre-baked mission bundle for {preset.name}.",
                done=1,
                total=1,
                session_id=preset.slug,
            )
            return

    session_id = (
        preset.slug
        if (output_dir_override is not None and preset is not None)
        else make_session_id(center.ra.deg, center.dec.deg, fov, settings.collections, settings.pipeline_version)
    )
    session_dir = output_dir_override or (settings.spx_cache_dir / "sessions" / session_id)
    lock_key = str(session_dir.resolve())

    async with _get_session_lock(lock_key):
        if output_dir_override is None and (session_dir / "manifest.json").exists():
            yield ProgressEvent(
                stage="done",
                message="Loaded cached science bundle.",
                done=1,
                total=1,
                session_id=session_id,
            )
            return

        cache = DiskCache(settings.spx_cache_dir)

        try:
            async with create_async_client(timeout_s=settings.spx_http_timeout_s) as client:
                records = await query_sia(client, float(center.ra.deg), float(center.dec.deg), settings.collections)
                n_cols = len({r.collection for r in records})
                yield ProgressEvent(
                    stage="query",
                    message=f"Found {len(records)} SPHEREx exposures across {n_cols} uniform release(s).",
                )

                passes, pass_map = group_passes(records, gap_days=settings.spx_pass_gap_days)
                if preset is not None:
                    center = propagate(preset, mid_epoch(passes))

                budget = per_pass_det_override if per_pass_det_override is not None else settings.spx_frames_per_pass_det
                selected = select(records, pass_map, per_pass_det=budget)

                yield ProgressEvent(
                    stage="plan",
                    message=f"Grouped into {len(passes)} survey passes · Fetching {len(selected)} balanced D1–D6 exposures.",
                    done=0,
                    total=len(selected),
                )

                sem = asyncio.Semaphore(settings.spx_max_workers)
                ra_center = float(center.ra.deg)
                dec_center = float(center.dec.deg)

                async def _fetch_one(rec):
                    async with sem:
                        return rec, await read_subimage(
                            client, cache, rec, ra_center, dec_center, fov, mode=settings.spx_fetch_mode
                        )

                tasks = [asyncio.create_task(_fetch_one(r)) for r in selected]
                fetched: list[tuple] = []
                errors = 0
                for idx, coro in enumerate(asyncio.as_completed(tasks), start=1):
                    try:
                        rec, sub = await coro
                        fetched.append((rec, sub))
                    except Exception:
                        errors += 1
                    yield ProgressEvent(
                        stage="fetch",
                        message=f"Fetched {idx}/{len(selected)} SPHEREx subimages (range-cropped & ZODI-ready)...",
                        done=idx,
                        total=len(selected),
                    )

                if not fetched:
                    raise ExploreError(
                        "FETCH_FAILED",
                        "Could not retrieve overlapping SPHEREx exposures for these coordinates.",
                        502,
                    )

                yield ProgressEvent(
                    stage="process",
                    message=f"Aligning {len(fetched)} exposures onto North-Up grid & building coadds/differences...",
                    done=len(selected),
                    total=len(selected),
                )

                grid_spec, grid_wcs = make_grid(center, fov)

                def _align_sync():
                    aligned = []
                    used_recs = []
                    for rec, sub in fetched:
                        cleaned = clean_subimage(
                            obs_id=rec.obs_id,
                            collection=rec.collection,
                            detector=rec.detector,
                            t_mid_mjd=rec.t_mid_mjd,
                            wavelength_um=sub["wavelength_um"],
                            raw_image=sub["image"],
                            raw_flags=sub["flags"],
                            raw_variance=sub["variance"],
                            raw_zodi=sub["zodi"],
                            wcs=sub["wcs"],
                            subtract_residual_sky=True,
                        )
                        aligned.append(align_frame(cleaned, grid_wcs, grid_spec.npix))
                        used_recs.append(rec)
                    prods = build_all_products(aligned, pass_map, passes, grid_spec.npix)
                    return prods, used_recs

                compiled_products, used_recs = await asyncio.to_thread(_align_sync)

                frames_dir = session_dir / "frames"
                frames_dir.mkdir(parents=True, exist_ok=True)
                prod_infos: dict[str, ProductInfo] = {}
                frames_meta: dict[str, list] = {}

                for name, prod in compiled_products.items():
                    blob = encode_framepack(prod.frame_ids, prod.data, prod.flags)
                    out_file = frames_dir / f"{name}.sfp"
                    out_file.write_bytes(blob)
                    prod_infos[name] = ProductInfo(
                        name=name,
                        url=f"/api/sessions/{session_id}/frames/{name}.sfp",
                        n_frames=len(prod.frame_ids),
                        planes_per_frame=prod.planes_per_frame,
                        has_flags=prod.flags is not None,
                        bytes=len(blob),
                    )
                    frames_meta[name] = prod.metas

                # Persist raw subimage cache index so live spectrum clicks resolve quickly
                raw_index = [
                    {
                        "obs_id": r.obs_id,
                        "detector": r.detector,
                        "ra_deg": ra_center,
                        "dec_deg": dec_center,
                        "fov_deg": fov,
                    }
                    for r in used_recs
                ]
                (session_dir / "raw_refs.json").write_text(json.dumps(raw_index), encoding="utf-8")

                warnings: list[str] = []
                if len(passes) < 2:
                    warnings.append("Only 1 SPHEREx survey pass found here so far; epoch difference frames are unavailable.")
                if errors > 0:
                    warnings.append(f"{errors} partial detector-edge exposures skipped cleanly.")
                if preset and preset.caveat:
                    warnings.append(preset.caveat)

                manifest = SessionManifest(
                    session_id=session_id,
                    source="preset" if source_kind == "preset" else "live",
                    target=TargetRef(
                        ra=round(ra_center, 6),
                        dec=round(dec_center, 6),
                        name=preset.name if preset else None,
                        slug=preset.slug if preset else None,
                        mjd_ref=round(mid_epoch(passes), 4),
                    ),
                    grid=grid_spec,
                    passes=passes,
                    products=prod_infos,
                    frames=frames_meta,
                    warnings=warnings,
                    citations=DEFAULT_CITATIONS,
                    created_utc=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    pipeline_version=settings.pipeline_version,
                )
                save_manifest(session_dir, manifest)

                if output_dir_override is None:
                    cache.evict_lru(settings.spx_cache_max_gb)

                yield ProgressEvent(
                    stage="done",
                    message=f"Ready! {len(passes)} passes and {len(used_recs)} exposures compiled.",
                    done=len(selected),
                    total=len(selected),
                    session_id=session_id,
                )

        except ExploreError as exc:
            yield ProgressEvent(stage="error", message=exc.message, error_code=exc.error_code)
        except Exception as exc:
            yield ProgressEvent(
                stage="error",
                message=f"Unexpected pipeline error: {exc}",
                error_code="PIPELINE_ERROR",
            )
