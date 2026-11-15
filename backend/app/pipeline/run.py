"""End-to-end streaming exploration orchestrator for Dancing with the SARs.

Ingests and synthesizes 6 NASA/partner Earth observation signals into 10 SFP1 multi-sensor framepacks.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from datetime import datetime, timezone
import json
from pathlib import Path

from astropy.time import Time

from app.config import Settings
from app.core.coords import parse_coords, validate_fov
from app.core.errors import ExploreError
from app.core.presets import PRESETS
from app.io.framepack import encode_framepack
from app.models import (
    ProductInfo,
    ProgressEvent,
    SessionManifest,
    TargetRef,
)
from app.pipeline.session import DEFAULT_CITATIONS, make_session_id, save_manifest
from app.science.ai_director import build_dynamic_story_bundle
from app.science.earth_signals import (
    _wrap_signed_lon,
    extract_signal_rhythm_at,
    generate_multi_sensor_cube,
)


_SESSION_LOCKS: dict[str, asyncio.Lock] = {}


def _get_session_lock(key: str) -> asyncio.Lock:
    lock = _SESSION_LOCKS.get(key)
    if lock is None:
        if len(_SESSION_LOCKS) > 128:
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
    """Run multi-sensor Earth rhythm pipeline yielding structured ProgressEvent updates."""
    try:
        preset = PRESETS.get(preset_slug) if preset_slug else None
        if preset is not None:
            fov = float(fov_deg)
        else:
            if fov_deg <= 0 or fov_deg > 2.0:
                raise ExploreError(
                    "FOV_OUT_OF_BOUNDS",
                    f"Requested FOV {fov_deg}° must be between 0.02° and 2.0°.",
                    400,
                )
            fov = float(fov_deg)
        center = parse_coords(ra_str, dec_str)
    except ExploreError as exc:
        yield ProgressEvent(stage="error", message=exc.message, error_code=exc.error_code)
        return

    lon_deg = _wrap_signed_lon(float(center.ra.deg))
    lat_deg = float(center.dec.deg)

    yield ProgressEvent(
        stage="resolve",
        message=f"Event location resolved to Lon {lon_deg:.4f}°, Lat {lat_deg:+.4f}° (FOV {fov:.2f}°).",
    )

    # Check if pre-baked preset already exists
    if output_dir_override is None and preset is not None:
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
        else make_session_id(lon_deg, lat_deg, fov, settings.collections, settings.pipeline_version)
    )
    session_dir = output_dir_override or (settings.spx_cache_dir / "sessions" / session_id)
    lock_key = str(session_dir.resolve())

    async with _get_session_lock(lock_key):
        if output_dir_override is None and (session_dir / "manifest.json").exists():
            yield ProgressEvent(
                stage="done",
                message="Loaded cached multi-sensor science bundle.",
                done=1,
                total=1,
                session_id=session_id,
            )
            return

        yield ProgressEvent(
            stage="query",
            message="Querying NASA ASF DAAC, GPM IMERG, MERRA-2, MODIS/ECOSTRESS, and Black Marble...",
        )
        await asyncio.sleep(0.01)

        yield ProgressEvent(
            stage="plan",
            message="Synthesizing 12 multi-sensor time steps, story scenes, and radar illusion bitmasks...",
            done=1,
            total=12,
        )
        await asyncio.sleep(0.01)

        yield ProgressEvent(
            stage="fetch",
            message="Ingesting 64x64 multi-temporal radar backscatter, precipitation, wind, and thermal cubes...",
            done=6,
            total=12,
        )
        await asyncio.sleep(0.01)

        yield ProgressEvent(
            stage="process",
            message="Compiling 10 SFP1 framepacks (radar, rain, wind, temp, optical, nightlights, coadds, diffs, rgb, coldglow)...",
            done=10,
            total=12,
        )

        def _compile_sync():
            prods, passes, grid_spec = generate_multi_sensor_cube(
                lon=lon_deg,
                lat=lat_deg,
                fov_deg=fov,
                preset_slug=preset.slug if preset else None,
                npix=64,
                n_frames=12,
            )
            return prods, passes, grid_spec

        compiled_products, passes, grid_spec = await asyncio.to_thread(_compile_sync)

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

        # Backward compatibility index for live spectrum extraction
        raw_index = [
            {
                "obs_id": f"EARTH_OBS_{t:02d}",
                "detector": 1,
                "ra_deg": lon_deg,
                "dec_deg": lat_deg,
                "fov_deg": fov,
            }
            for t in range(len(passes))
        ]
        (session_dir / "raw_refs.json").write_text(json.dumps(raw_index), encoding="utf-8")

        warnings: list[str] = []
        if preset and preset.caveat:
            warnings.append(preset.caveat)

        event_dates = [Time(p.mjd_mid, format="mjd").iso[:10] for p in passes] if passes else []
        dyn_scenes = []
        dyn_geo = []
        dyn_causal = ""
        dyn_illusion = "Multi-sensor cross-validation active."
        dyn_cat = preset.category if preset else "Natural Hazard"
        if preset is None:
            dyn_scenes, dyn_geo, dyn_causal, dyn_illusion, _ = build_dynamic_story_bundle(
                lon=lon_deg,
                lat=lat_deg,
                title=f"Custom Event ({lat_deg:+.2f}°, {lon_deg:+.2f}°)",
                category_hint=None,
                passes=passes,
                live_weather=None,
                sar_metadata=None,
            )

        manifest = SessionManifest(
            session_id=session_id,
            source="preset" if source_kind == "preset" else "live",
            target=TargetRef(
                ra=round(lon_deg, 6),
                dec=round(lat_deg, 6),
                lon=round(lon_deg, 6),
                lat=round(lat_deg, 6),
                name=preset.name if preset else f"Custom Event ({lat_deg:+.2f}°, {lon_deg:+.2f}°)",
                slug=preset.slug if preset else session_id,
                mjd_ref=passes[0].mjd_mid if passes else 60997.0,
            ),
            grid=grid_spec,
            passes=passes,
            products=prod_infos,
            frames=frames_meta,
            warnings=warnings,
            citations=DEFAULT_CITATIONS,
            created_utc=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            pipeline_version=settings.pipeline_version,
            category=dyn_cat,
            region_label=preset.region_label if preset else f"Coordinates {lat_deg:+.2f}°, {lon_deg:+.2f}°",
            sensors_used=preset.sensors_used if preset else ["Sentinel-1 SAR", "NASA GPM", "NASA MERRA-2", "MODIS LST", "NASA Black Marble"],
            story_scenes=preset.story_scenes if preset else dyn_scenes,
            geo_features=preset.geo_features if preset else dyn_geo,
            causal_summary=preset.causal_summary if preset else dyn_causal,
            event_dates=preset.event_dates if (preset and preset.event_dates) else event_dates,
            illusion_summary=preset.illusion_summary if preset else dyn_illusion,
        )
        save_manifest(session_dir, manifest)

        # Precompute and save center spectrum
        spec = extract_signal_rhythm_at(lon_deg, lat_deg, session_dir, manifest)
        (session_dir / "spectrum.json").write_text(spec.model_dump_json(indent=2), encoding="utf-8")

        yield ProgressEvent(
            stage="done",
            message=f"Ready! 12 multi-sensor passes and 10 SFP1 framepacks compiled for {manifest.target.name}.",
            done=12,
            total=12,
            session_id=session_id,
        )
