"""Survey-pass clustering and balanced multi-detector frame selection."""

from collections import defaultdict
from astropy.time import Time

from app.models import ExposureRecord, SurveyPass


def _mjd_span_label(index: int, mjd_start: float, mjd_end: float) -> str:
    """Format concise human-readable pass label like 'Pass 1 · May 2025'."""
    dt_start = Time(mjd_start, format="mjd", scale="utc").to_datetime()
    dt_end = Time(mjd_end, format="mjd", scale="utc").to_datetime()
    m1 = dt_start.strftime("%b %Y")
    m2 = dt_end.strftime("%b %Y")
    if m1 == m2:
        span = m1
    elif dt_start.year == dt_end.year:
        span = f"{dt_start.strftime('%b')}–{m2}"
    else:
        span = f"{m1}–{m2}"
    return f"Pass {index + 1} · {span}"


def group_passes(
    records: list[ExposureRecord],
    gap_days: float = 45.0,
) -> tuple[list[SurveyPass], dict[tuple[str, int], int]]:
    """Split exposures chronologically into discrete sky passes at temporal gaps > gap_days."""
    if not records:
        return [], {}

    sorted_recs = sorted(records, key=lambda r: (r.t_mid_mjd, r.detector, r.obs_id))
    clusters: list[list[ExposureRecord]] = []
    for rec in sorted_recs:
        if not clusters or (rec.t_mid_mjd - clusters[-1][-1].t_mid_mjd) > gap_days:
            clusters.append([rec])
        else:
            clusters[-1].append(rec)

    passes: list[SurveyPass] = []
    pass_map: dict[tuple[str, int], int] = {}
    for idx, group in enumerate(clusters):
        mjd_start = min(r.t_mid_mjd for r in group)
        mjd_end = max(r.t_mid_mjd for r in group)
        mjd_mid = 0.5 * (mjd_start + mjd_end)
        passes.append(
            SurveyPass(
                index=idx,
                mjd_start=mjd_start,
                mjd_end=mjd_end,
                mjd_mid=mjd_mid,
                n_exposures=len(group),
                label=_mjd_span_label(idx, mjd_start, mjd_end),
            )
        )
        for rec in group:
            pass_map[(rec.obs_id, rec.detector)] = idx

    return passes, pass_map


def select(
    records: list[ExposureRecord],
    pass_map: dict[tuple[str, int], int],
    per_pass_det: int = 4,
) -> list[ExposureRecord]:
    """Select an evenly time-distributed subset across every (pass, detector) bucket."""
    if per_pass_det <= 0:
        return sorted(records, key=lambda r: (r.t_mid_mjd, r.detector, r.obs_id))

    buckets: dict[tuple[int, int], list[ExposureRecord]] = defaultdict(list)
    for rec in records:
        p_idx = pass_map[(rec.obs_id, rec.detector)]
        buckets[(p_idx, rec.detector)].append(rec)

    chosen: list[ExposureRecord] = []
    for (_, _), bucket in sorted(buckets.items()):
        bucket.sort(key=lambda r: (r.t_mid_mjd, r.obs_id))
        n = len(bucket)
        if n <= per_pass_det:
            chosen.extend(bucket)
        elif per_pass_det == 1:
            chosen.append(bucket[n // 2])
        else:
            indices = sorted({round(i * (n - 1) / (per_pass_det - 1)) for i in range(per_pass_det)})
            chosen.extend(bucket[idx] for idx in indices)

    chosen.sort(key=lambda r: (r.t_mid_mjd, r.detector, r.obs_id))
    return chosen
