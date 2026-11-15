"""Pydantic API contract shared between FastAPI backend and React frontend."""

from typing import Any, Literal
from pydantic import BaseModel, Field, model_validator


SignalId = Literal["radar", "rain", "wind", "temp", "optical", "nightlights"]
TargetKind = Literal["mover", "variable", "binary_bd", "flood", "wildfire", "drought", "agriculture", "cryosphere"]
LensId = Literal["motion", "coldglow", "variable", "rgb", "visits", "radar", "rain", "wind", "temp", "optical", "nightlights"]
StretchFn = Literal["asinh", "linear", "log"]
OverlaySource = Literal["preset", "live", "unavailable"]
PatternKind = Literal["onset", "peak_impact", "blackout", "illusion", "mover", "variable", "cold_ir", "archive_drift"]


class CameraView(BaseModel):
    """Multi-scale geographic camera keyframe for Story-Map playback."""

    lat: float
    lon: float
    zoom: float = 9.0
    bbox: list[float] = Field(default_factory=list)  # [west, south, east, north]
    region_name: str = ""


class CausalLink(BaseModel):
    """Directed cause-and-effect relationship between connected Earth datasets."""

    from_signal: str
    to_signal: str
    lag_hours: int = 0
    correlation: float = 0.85
    explanation: str = ""
    from_coord: list[float] = Field(default_factory=list)  # [lat, lon]
    to_coord: list[float] = Field(default_factory=list)  # [lat, lon]


class GeoFeatureOverlay(BaseModel):
    """Geographic map feature rendered cleanly on the Leaflet Story Map."""

    id: str
    kind: str
    label: str
    detail: str
    geometry_type: Literal["polygon", "polyline", "point_radius"]
    coordinates: list[Any] = Field(default_factory=list)
    radius_km: float | None = None
    color: str = "#38bdf8"
    scene_indices: list[int] = Field(default_factory=list)


class StoryScene(BaseModel):
    """AI Story Director narrative scene card with camera & causal links."""

    index: int
    phase: str
    title: str
    date_label: str
    frame_index: int
    active_layers: list[SignalId]
    narration: str
    why_these_layers: str
    illusion_note: str
    camera: CameraView | None = None
    causal_chain: list[CausalLink] = Field(default_factory=list)
    key_metrics: dict[str, str] = Field(default_factory=dict)
    gibs_layer: str | None = None
    gibs_date: str | None = None
    sar_granule_id: str | None = None


class TargetPreset(BaseModel):
    """Official benchmark mission preset shown on landing cards."""

    slug: str
    name: str
    kind: TargetKind = "mover"
    ra_deg: float
    dec_deg: float
    lon: float | None = None
    lat: float | None = None
    title: str | None = None
    ref_epoch: float = 2026.0
    pmra_masyr: float | None = None
    pmdec_masyr: float | None = None
    coord_note: str | None = None
    default_fov: float = 0.5
    default_lens: LensId = "motion"
    mission_title: str = ""
    summary: str = ""
    mission_steps: list[str] = Field(default_factory=list)
    what_to_expect: str = ""
    caveat: str | None = None
    has_preset_bundle: bool = False
    category: str = ""
    region_label: str = ""
    sensors_used: list[str] = Field(default_factory=list)
    story_scenes: list[StoryScene] = Field(default_factory=list)
    illusion_summary: str = ""
    causal_summary: str = ""
    event_dates: list[str] = Field(default_factory=list)
    geo_features: list[GeoFeatureOverlay] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _sync_coords_and_titles(cls, data: Any) -> Any:
        if isinstance(data, dict):
            # Synchronize lon <-> ra_deg and lat <-> dec_deg
            if "lon" in data and "ra_deg" not in data:
                data["ra_deg"] = data["lon"]
            elif "ra_deg" in data and "lon" not in data:
                data["lon"] = data["ra_deg"]
            if "lat" in data and "dec_deg" not in data:
                data["dec_deg"] = data["lat"]
            elif "dec_deg" in data and "lat" not in data:
                data["lat"] = data["dec_deg"]
            # Synchronize name <-> title <-> mission_title
            title = data.get("title") or data.get("name") or data.get("mission_title")
            if title:
                data.setdefault("title", title)
                data.setdefault("name", title)
                data.setdefault("mission_title", title)
        return data


class ExposureRecord(BaseModel):
    """Single observation record discovered via remote archive."""

    obs_id: str
    collection: str
    detector: int
    t_mid_mjd: float
    em_min_um: float
    em_max_um: float
    access_url: str


class SurveyPass(BaseModel):
    """Contiguous time step or satellite revisit pass."""

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
    kind: Literal["visit", "coadd", "diff", "coldglow", "rgb", "signal"]
    pass_index: int
    pass_label: str
    detector: int | None = None
    mjd: float
    date_utc: str
    wavelength_um: float | None = None
    obs_ids: list[str] = Field(default_factory=list)
    flag_summary: dict[str, int] = Field(default_factory=dict)
    n_inputs: int = 1
    stretch_hint: StretchHint
    ref_pass_index: int | None = None
    mean_flux_center: float | None = None
    signal: SignalId | None = None
    unit: str | None = None


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
    lon: float | None = None
    lat: float | None = None
    name: str | None = None
    slug: str | None = None
    mjd_ref: float | None = None

    @model_validator(mode="before")
    @classmethod
    def _sync_coords(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "lon" in data and "ra" not in data:
                data["ra"] = data["lon"]
            elif "ra" in data and "lon" not in data:
                data["lon"] = data["ra"]
            if "lat" in data and "dec" not in data:
                data["dec"] = data["lat"]
            elif "dec" in data and "lat" not in data:
                data["lat"] = data["dec"]
        return data


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
    """Complete scientific manifest returned to the client for one session."""

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
    category: str = ""
    region_label: str = ""
    sensors_used: list[str] = Field(default_factory=list)
    story_scenes: list[StoryScene] = Field(default_factory=list)
    illusion_summary: str = ""
    causal_summary: str = ""
    event_dates: list[str] = Field(default_factory=list)
    geo_features: list[GeoFeatureOverlay] = Field(default_factory=list)


class AiExplainRequest(BaseModel):
    """Request for the 2-Tier AI Causal Analyst explaining dataset links."""

    session_id: str | None = None
    question: str = "Why did these datasets change in sequence?"
    scene_index: int = 0
    lat: float | None = None
    lon: float | None = None
    illusion_guard: bool = True


class AiExplainResponse(BaseModel):
    """AI Causal Analyst answer detailing dataset coupling and radar physics."""

    answer: str
    mode: Literal["causal_graph", "gemini_enhanced"] = "causal_graph"
    recommended_layers: list[SignalId] = Field(default_factory=lambda: ["radar", "rain", "wind"])
    key_connections: list[str] = Field(default_factory=list)
    lead_lag_summary: str = ""


class SpectrumPoint(BaseModel):
    """Single flux or measurement point for backward compatibility."""

    wavelength_um: float = 0.0
    flux_mjysr: float = 0.0
    err: float = 0.0
    detector: int = 1
    mjd: float = 0.0
    obs_id: str = ""
    flagged: bool = False


class SpectrumResult(BaseModel):
    """Multi-sensor rhythm time series extracted at clicked Earth coordinates."""

    ra: float
    dec: float
    lon: float | None = None
    lat: float | None = None
    series: dict[str, list[float]] = Field(default_factory=dict)
    dates: list[str] = Field(default_factory=list)
    units: dict[str, str] = Field(default_factory=dict)
    location_story: str = ""
    points: list[SpectrumPoint] = Field(default_factory=list)
    aperture_arcsec: float = 6.15
    n_used: int = 0
    n_rejected: int = 0
    note: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _sync_coords(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "lon" in data and "ra" not in data:
                data["ra"] = data["lon"]
            elif "ra" in data and "lon" not in data:
                data["lon"] = data["ra"]
            if "lat" in data and "dec" not in data:
                data["dec"] = data["lat"]
            elif "dec" in data and "lat" not in data:
                data["lat"] = data["dec"]
        return data


class GaiaSource(BaseModel):
    """Astrometric catalog source."""

    source_id: str
    ra: float
    dec: float
    g_mag: float | None = None
    pmra: float | None = None
    pmdec: float | None = None
    ra_at_mjd: float
    dec_at_mjd: float


class AllwiseSource(BaseModel):
    """Infrared catalog counterpart."""

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
    mjd_ref: float = 2026.0
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

    irsa_ok: bool = True
    cache_entries: int = 0
    presets_ready: list[str] = Field(default_factory=list)
    version: str = "2.0.0"


class PatternCandidate(BaseModel):
    """Automatically detected spatial, temporal, or illusion anomaly in a multi-sensor cube."""

    id: str
    kind: PatternKind
    title: str
    summary: str
    confidence: Literal["High", "Medium"]
    snr: float
    ra: float
    dec: float
    fits_x: float
    fits_y: float
    past_fits_x: float | None = None
    past_fits_y: float | None = None
    suggested_label: str
    metrics: dict[str, float | str] = Field(default_factory=dict)


class PatternReport(BaseModel):
    """Ranked list of automated spatial/temporal/spectral patterns for a session."""

    session_id: str
    n_patterns: int
    summary: str
    past_label: str | None = None
    present_label: str | None = None
    candidates: list[PatternCandidate] = Field(default_factory=list)
