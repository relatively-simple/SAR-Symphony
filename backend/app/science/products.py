"""Science display products derived from aligned SPHEREx exposures."""

from collections import defaultdict
from dataclasses import dataclass
import numpy as np
from astropy.time import Time

from app.core.detectors import DETECTORS
from app.core.flags import COMPACT_BITS, summarize_uint16_flags
from app.models import FrameMeta, StretchHint, SurveyPass
from app.science.align import AlignedFrame
from app.science.coadd import CoaddResult, coadd_ivar


_MISSING_BIT = 1 << next(pos for pos, name, _ in COMPACT_BITS if name == "MISSING_DATA")


def _mjd_to_iso(mjd: float) -> str:
    return Time(mjd, format="mjd", scale="utc").strftime("%Y-%m-%d %H:%M UTC")


def compute_stretch_hint(plane: np.ndarray, *, symmetric: bool = False) -> StretchHint:
    """Compute robust percentile or symmetric noise-scaled clip bounds for Canvas rendering."""
    vals = plane[np.isfinite(plane)]
    if vals.size == 0:
        return StretchHint(p_lo=-1.0, p_hi=1.0) if symmetric else StretchHint(p_lo=0.0, p_hi=1.0)

    if symmetric:
        med = float(np.median(vals))
        mad = float(np.median(np.abs(vals - med)))
        sigma = max(1.4826 * mad, float(np.percentile(np.abs(vals), 90)) * 0.3, 1e-6)
        bound = 5.0 * sigma
        return StretchHint(p_lo=-bound, p_hi=bound)

    p_lo = float(np.percentile(vals, 2.0))
    p_hi = float(np.percentile(vals, 99.5))
    if p_hi <= p_lo:
        p_hi = p_lo + 1.0
    return StretchHint(p_lo=p_lo, p_hi=p_hi)


def _center_mean(plane: np.ndarray) -> float | None:
    """Measure mean intensity in central aperture box (used for Variable Watch sparkline)."""
    h, w = plane.shape
    r = max(2, min(h, w) // 10)
    cy, cx = h // 2, w // 2
    box = plane[cy - r : cy + r + 1, cx - r : cx + r + 1]
    vals = box[np.isfinite(box)]
    return float(np.mean(vals)) if vals.size > 0 else None


@dataclass
class CompiledProduct:
    """Compiled binary tensor plus traceable frame metadata for one SFP1 file."""

    name: str
    frame_ids: list[str]
    data: np.ndarray
    flags: np.ndarray | None
    metas: list[FrameMeta]
    planes_per_frame: int


def build_all_products(
    aligned_frames: list[AlignedFrame],
    pass_map: dict[tuple[str, int], int],
    passes: list[SurveyPass],
    npix: int,
) -> dict[str, CompiledProduct]:
    """Build pass_coadds, diffs, coldglow, rgb, and visits from aligned exposures."""
    by_pass_det: dict[tuple[int, int], list[AlignedFrame]] = defaultdict(list)
    for fr in aligned_frames:
        p_idx = pass_map[(fr.obs_id, fr.detector)]
        by_pass_det[(p_idx, fr.detector)].append(fr)

    # 1. Per-(pass, detector) inverse-variance coadds
    coadds: dict[tuple[int, int], CoaddResult] = {}
    coadd_ids: list[str] = []
    coadd_planes: list[np.ndarray] = []
    coadd_flags: list[np.ndarray] = []
    coadd_metas: list[FrameMeta] = []

    pass_by_idx = {p.index: p for p in passes}
    for (p_idx, det), group in sorted(by_pass_det.items()):
        c = coadd_ivar(group)
        coadds[(p_idx, det)] = c
        fid = f"coadd_p{p_idx}_d{det}"
        coadd_ids.append(fid)
        coadd_planes.append(c.image)
        coadd_flags.append(c.flags_u16)
        coadd_metas.append(
            FrameMeta(
                id=fid,
                kind="coadd",
                pass_index=p_idx,
                pass_label=pass_by_idx[p_idx].label,
                detector=det,
                mjd=c.mjd_mid,
                date_utc=_mjd_to_iso(c.mjd_mid),
                wavelength_um=round(c.wavelength_um, 3),
                obs_ids=c.obs_ids,
                flag_summary=c.flag_summary,
                n_inputs=c.n_inputs,
                stretch_hint=compute_stretch_hint(c.image, symmetric=False),
                mean_flux_center=_center_mean(c.image),
            )
        )

    products: dict[str, CompiledProduct] = {}
    if coadd_planes:
        products["pass_coadds"] = CompiledProduct(
            name="pass_coadds",
            frame_ids=coadd_ids,
            data=np.stack(coadd_planes, axis=0)[:, np.newaxis, :, :],
            flags=np.stack(coadd_flags, axis=0),
            metas=coadd_metas,
            planes_per_frame=1,
        )

    # 2. Per-detector Epoch N - Epoch 0 difference images (requires >=2 passes for same detector)
    diff_ids: list[str] = []
    diff_planes: list[np.ndarray] = []
    diff_flags: list[np.ndarray] = []
    diff_metas: list[FrameMeta] = []

    for det in range(1, 7):
        avail_passes = sorted(p for (p, d) in coadds if d == det)
        if len(avail_passes) < 2:
            continue
        ref_p = avail_passes[0]
        ref_c = coadds[(ref_p, det)]
        for tgt_p in avail_passes[1:]:
            tgt_c = coadds[(tgt_p, det)]
            diff_img = (tgt_c.image - ref_c.image).astype(np.float32)
            diff_flg = (tgt_c.flags_u16 | ref_c.flags_u16).astype(np.uint16)
            diff_flg[~np.isfinite(diff_img)] |= np.uint16(_MISSING_BIT)
            fid = f"diff_p{tgt_p}_minus_p{ref_p}_d{det}"
            diff_ids.append(fid)
            diff_planes.append(diff_img)
            diff_flags.append(diff_flg)
            diff_metas.append(
                FrameMeta(
                    id=fid,
                    kind="diff",
                    pass_index=tgt_p,
                    pass_label=f"{pass_by_idx[tgt_p].label} − {pass_by_idx[ref_p].label}",
                    detector=det,
                    mjd=tgt_c.mjd_mid,
                    date_utc=_mjd_to_iso(tgt_c.mjd_mid),
                    wavelength_um=DETECTORS[det].lam_mid_um,
                    obs_ids=ref_c.obs_ids + tgt_c.obs_ids,
                    flag_summary=summarize_uint16_flags(diff_flg),
                    n_inputs=ref_c.n_inputs + tgt_c.n_inputs,
                    stretch_hint=compute_stretch_hint(diff_img, symmetric=True),
                    ref_pass_index=ref_p,
                )
            )

    if diff_planes:
        products["diffs"] = CompiledProduct(
            name="diffs",
            frame_ids=diff_ids,
            data=np.stack(diff_planes, axis=0)[:, np.newaxis, :, :],
            flags=np.stack(diff_flags, axis=0),
            metas=diff_metas,
            planes_per_frame=1,
        )

    # 3. Cold Glow (D5+D6 combined per pass for brown dwarfs / Planet X)
    cg_ids: list[str] = []
    cg_planes: list[np.ndarray] = []
    cg_flags: list[np.ndarray] = []
    cg_metas: list[FrameMeta] = []

    for p in passes:
        pool = by_pass_det.get((p.index, 5), []) + by_pass_det.get((p.index, 6), [])
        if not pool:
            continue
        c = coadd_ivar(pool)
        fid = f"coldglow_p{p.index}"
        cg_ids.append(fid)
        cg_planes.append(c.image)
        cg_flags.append(c.flags_u16)
        cg_metas.append(
            FrameMeta(
                id=fid,
                kind="coldglow",
                pass_index=p.index,
                pass_label=p.label,
                detector=None,
                mjd=c.mjd_mid,
                date_utc=_mjd_to_iso(c.mjd_mid),
                wavelength_um=round(c.wavelength_um, 3),
                obs_ids=c.obs_ids,
                flag_summary=c.flag_summary,
                n_inputs=c.n_inputs,
                stretch_hint=compute_stretch_hint(c.image, symmetric=False),
                mean_flux_center=_center_mean(c.image),
            )
        )

    if cg_planes:
        products["coldglow"] = CompiledProduct(
            name="coldglow",
            frame_ids=cg_ids,
            data=np.stack(cg_planes, axis=0)[:, np.newaxis, :, :],
            flags=np.stack(cg_flags, axis=0),
            metas=cg_metas,
            planes_per_frame=1,
        )

    # 4. IR False-Color RGB (R=D6/D5, G=D4/D3, B=D2/D1) per pass
    rgb_ids: list[str] = []
    rgb_cubes: list[np.ndarray] = []
    rgb_flags: list[np.ndarray] = []
    rgb_metas: list[FrameMeta] = []

    for p in passes:
        ch_blue = coadds.get((p.index, 2)) or coadds.get((p.index, 1))
        ch_green = coadds.get((p.index, 4)) or coadds.get((p.index, 3))
        ch_red = coadds.get((p.index, 6)) or coadds.get((p.index, 5))
        present = [c for c in (ch_red, ch_green, ch_blue) if c is not None]
        if len(present) < 2:
            continue

        def _norm_channel(coadd_res: CoaddResult | None) -> np.ndarray:
            if coadd_res is None:
                return np.zeros((npix, npix), dtype=np.float32)
            hint = compute_stretch_hint(coadd_res.image, symmetric=False)
            span = max(hint.p_hi - hint.p_lo, 1e-6)
            scaled = (coadd_res.image - hint.p_lo) / span
            return np.where(np.isfinite(scaled), np.clip(scaled, 0.0, 2.0), np.nan).astype(np.float32)

        cube = np.stack([_norm_channel(ch_red), _norm_channel(ch_green), _norm_channel(ch_blue)], axis=0)
        u_flags = np.bitwise_or.reduce([c.flags_u16 for c in present]).astype(np.uint16)
        fid = f"rgb_p{p.index}"
        rgb_ids.append(fid)
        rgb_cubes.append(cube)
        rgb_flags.append(u_flags)
        obs_all = [oid for c in present for oid in c.obs_ids]
        rgb_metas.append(
            FrameMeta(
                id=fid,
                kind="rgb",
                pass_index=p.index,
                pass_label=p.label,
                detector=None,
                mjd=float(np.mean([c.mjd_mid for c in present])),
                date_utc=_mjd_to_iso(float(np.mean([c.mjd_mid for c in present]))),
                wavelength_um=None,
                obs_ids=obs_all,
                flag_summary=summarize_uint16_flags(u_flags),
                n_inputs=sum(c.n_inputs for c in present),
                stretch_hint=StretchHint(p_lo=0.0, p_hi=1.0),
            )
        )

    if rgb_cubes:
        products["rgb"] = CompiledProduct(
            name="rgb",
            frame_ids=rgb_ids,
            data=np.stack(rgb_cubes, axis=0),
            flags=np.stack(rgb_flags, axis=0),
            metas=rgb_metas,
            planes_per_frame=3,
        )

    # 5. Raw wavelength-labelled single visits (Pro flipbook)
    sorted_visits = sorted(aligned_frames, key=lambda f: (f.t_mid_mjd, f.detector, f.obs_id))
    if sorted_visits:
        visit_ids: list[str] = []
        visit_planes: list[np.ndarray] = []
        visit_flags: list[np.ndarray] = []
        visit_metas: list[FrameMeta] = []
        for idx, fr in enumerate(sorted_visits):
            p_idx = pass_map[(fr.obs_id, fr.detector)]
            fid = f"visit_{idx}_{fr.obs_id}_d{fr.detector}"
            visit_ids.append(fid)
            visit_planes.append(fr.image)
            visit_flags.append(fr.flags_u16)
            visit_metas.append(
                FrameMeta(
                    id=fid,
                    kind="visit",
                    pass_index=p_idx,
                    pass_label=pass_by_idx[p_idx].label,
                    detector=fr.detector,
                    mjd=fr.t_mid_mjd,
                    date_utc=_mjd_to_iso(fr.t_mid_mjd),
                    wavelength_um=round(fr.wavelength_um, 3),
                    obs_ids=[fr.obs_id],
                    flag_summary=fr.flag_summary,
                    n_inputs=1,
                    stretch_hint=compute_stretch_hint(fr.image, symmetric=False),
                )
            )
        products["visits"] = CompiledProduct(
            name="visits",
            frame_ids=visit_ids,
            data=np.stack(visit_planes, axis=0)[:, np.newaxis, :, :],
            flags=np.stack(visit_flags, axis=0),
            metas=visit_metas,
            planes_per_frame=1,
        )

    return products
