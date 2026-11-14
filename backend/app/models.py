"""Pydantic API contract shared between FastAPI backend and React frontend."""

from typing import Literal
from pydantic import BaseModel, Field


TargetKind = Literal["mover", "variable", "binary_bd"]
LensId = Literal["motion", "coldglow", "variable", "rgb", "visits"]
StretchFn = Literal["asinh", "linear", "log"]
OverlaySource = Literal["preset", "live", "unavailable"]


class TargetPreset(BaseModel):
    """Official benchmark mission preset shown on landing cards."""

    slug: str
    name: str
    kind: TargetKind
    ra_deg: float
    dec_deg: float
    ref_epoch: float
    pmra_masyr: float | None = None
    pmdec_masyr: float | None = None
    coord_note: str | None = None
    default_fov: float = 0.05
    default_lens: LensId = "motion"
    mission_title: str
    summary: str
    mission_steps: list[str]
    what_to_expect: str
    caveat: str | None = None
    has_preset_bundle: bool = False


class ExposureRecord(BaseModel):
    """Single SPHEREx spectral image discovered via IRSA SIAv2."""

    obs_id: str
    collection: str
    detector: int
    t_mid_mjd: float
    em_min_um: float
    em_max_um: float
    access_url: str


class SurveyPass(BaseModel):
    """Contiguous multi-day sky survey pass separated from neighbors by > gap_days."""

    index: int
    mjd_start: float
    mjd_end: float
    mjd_mid: float
    n_exposures: int
    label: str


class StretchHint(BaseModel):
    """Initial display percentile clip for browser canvas rendering."""

    p_lo: float
    p_hi: float


class FrameMeta(BaseModel):
    """Traceability metadata for a single plane/frame in an SFP1 binary bundle."""

    id: str
    kind: Literal["visit", "coadd", "diff", "coldglow", "rgb"]
    pass_index: int
    pass_label: str
    detector: int | None = None
    mjd: float
    date_utc: str
    wavelength_um: float | None = None
    obs_ids: list[str]
    flag_summary: dict[str, int] = Field(default_factory=dict)
    n_inputs: int = 1
    stretch_hint: StretchHint
    ref_pass_index: int | None = None
    mean_flux_center: float | None = None


class GridSpec(BaseModel):
    """Shared North-Up TAN WCS output grid specification."""

    ra0: float
    dec0: float
    fov_deg: float
    npix: int
    pixscale_arcsec: float = 6.15
    ctype: tuple[str, str] = ("RA---TAN", "DEC--TAN")
    north_up: bool = True


class TargetRef(BaseModel):
    """Resolved coordinate center and optional target metadata."""

    ra: float
    dec: float
    name: str | None = None
    slug: str | None = None
    mjd_ref: float | None = None


class ProductInfo(BaseModel):
    """Manifest pointer to one compiled SFP1 binary frame pack."""

    name: str
    url: str
    n_frames: int
    planes_per_frame: int
    has_flags: bool
    bytes: int


class CitationEntry(BaseModel):
    """Dataset citation or acknowledgment displayed cleanly in UI."""

    label: str
    doi: str | None = None
    url: str | None = None
    text: str


class SessionManifest(BaseModel):
    """Complete scientific manifest returned to the client for one sky session."""

    session_id: str
    source: Literal["preset", "live"]
    target: TargetRef
    grid: GridSpec
    passes: list[SurveyPass]
    products: dict[str, ProductInfo]
    frames: dict[str, list[FrameMeta]]
    warnings: list[str] = Field(default_factory=list)
    citations: list[CitationEntry] = Field(default_factory=list)
    created_utc: str
    pipeline_version: str


class SpectrumPoint(BaseModel):
    """Single aperture flux measurement from one SPHEREx visit."""

    wavelength_um: float
    flux_mjysr: float
    err: float
    detector: int
    mjd: float
    obs_id: str
    flagged: bool = False


class SpectrumResult(BaseModel):
    """On-the-fly multi-detector spectrum extracted at clicked sky coordinates."""

    ra: float
    dec: float
    points: list[SpectrumPoint]
    aperture_arcsec: float
    n_used: int
    n_rejected: int
    note: str | None = None


class GaiaSource(BaseModel):
    """Gaia DR3 star with position propagated from J2016.0 to SPHEREx epoch."""

    source_id: str
    ra: float
    dec: float
    g_mag: float | None = None
    pmra: float | None = None
    pmdec: float | None = None
    ra_at_mjd: float
    dec_at_mjd: float


class AllwiseSource(BaseModel):
    """AllWISE infrared catalog counterpart."""

    designation: str
    ra: float
    dec: float
    w1: float | None = None
    w2: float | None = None


class OverlaySet(BaseModel):
    """Cross-mission catalog overlays returned to the viewer canvas."""

    gaia: list[GaiaSource] = Field(default_factory=list)
    allwise: list[AllwiseSource] = Field(default_factory=list)
    source: OverlaySource = "unavailable"
    mjd_ref: float
    note: str | None = None


class ProgressEvent(BaseModel):
    """SSE progress update yielded during /api/explore execution."""

    stage: Literal["resolve", "query", "plan", "fetch", "process", "done", "error"]
    message: str
    done: int = 0
    total: int = 0
    session_id: str | None = None
    error_code: str | None = None


class HealthStatus(BaseModel):
    """Runtime health & preset availability summary."""

    irsa_ok: bool
    cache_entries: int
    presets_ready: list[str]
    version: str
