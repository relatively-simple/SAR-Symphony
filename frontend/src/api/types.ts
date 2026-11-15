export type SignalId = "radar" | "rain" | "wind" | "temp" | "optical" | "nightlights";

export type TargetKind =
  | "mover"
  | "variable"
  | "binary_bd"
  | "flood"
  | "wildfire"
  | "drought"
  | "agriculture"
  | "cryosphere";

export type LensId =
  | "blink"
  | "motion"
  | "coldglow"
  | "variable"
  | "rgb"
  | "visits"
  | "radar"
  | "rain"
  | "wind"
  | "temp"
  | "optical"
  | "nightlights";

export type StretchFn = "asinh" | "linear" | "log";
export type OverlaySource = "preset" | "live" | "unavailable";

export type PatternKind =
  | "onset"
  | "peak_impact"
  | "blackout"
  | "illusion"
  | "mover"
  | "variable"
  | "cold_ir"
  | "archive_drift";

export type ViewLayout = "single" | "compare";

export interface CameraView {
  lat: number;
  lon: number;
  zoom: number;
  bbox?: number[] | null;
  region_name: string;
}

export interface CausalLink {
  from_signal: string;
  to_signal: string;
  lag_hours: number;
  correlation: number;
  explanation: string;
  from_coord?: [number, number] | null;
  to_coord?: [number, number] | null;
}

export interface GeoFeatureOverlay {
  id: string;
  kind: string;
  label: string;
  detail: string;
  geometry_type: "point" | "point_radius" | "polyline" | "polygon";
  coordinates: any;
  radius_km?: number | null;
  color: string;
  scene_indices: number[];
}

export interface StoryScene {
  index: number;
  phase: string;
  title: string;
  date_label: string;
  frame_index: number;
  active_layers: SignalId[];
  narration: string;
  why_these_layers: string;
  illusion_note: string;
  camera?: CameraView | null;
  causal_chain?: CausalLink[];
  key_metrics?: Record<string, string | number>;
  gibs_layer?: string | null;
  gibs_date?: string | null;
  sar_granule_id?: string | null;
}

export interface TargetPreset {
  slug: string;
  name: string;
  kind: TargetKind;
  ra_deg: number;
  dec_deg: number;
  lon?: number;
  lat?: number;
  title?: string;
  ref_epoch: number;
  pmra_masyr?: number | null;
  pmdec_masyr?: number | null;
  coord_note?: string | null;
  default_fov: number;
  default_lens: LensId;
  mission_title: string;
  summary: string;
  mission_steps: string[];
  what_to_expect: string;
  caveat?: string | null;
  has_preset_bundle: boolean;
  category?: string;
  region_label?: string;
  sensors_used?: string[];
  story_scenes?: StoryScene[];
  illusion_summary?: string;
  causal_summary?: string;
  event_dates?: string[];
  geo_features?: GeoFeatureOverlay[];
}

export interface SurveyPass {
  index: number;
  mjd_start: number;
  mjd_end: number;
  mjd_mid: number;
  n_exposures: number;
  label: string;
}

export interface StretchHint {
  p_lo: number;
  p_hi: number;
}

export interface FrameMeta {
  id: string;
  kind: "visit" | "coadd" | "diff" | "coldglow" | "rgb";
  pass_index: number;
  pass_label: string;
  detector?: number | null;
  mjd: number;
  date_utc: string;
  wavelength_um?: number | null;
  obs_ids: string[];
  flag_summary: Record<string, number>;
  n_inputs: number;
  stretch_hint: StretchHint;
  ref_pass_index?: number | null;
  mean_flux_center?: number | null;
}

export interface GridSpec {
  ra0: number;
  dec0: number;
  fov_deg: number;
  npix: number;
  pixscale_arcsec: number;
  ctype: [string, string];
  north_up: boolean;
}

export interface TargetRef {
  ra: number;
  dec: number;
  lon?: number;
  lat?: number;
  name?: string | null;
  slug?: string | null;
  mjd_ref?: number | null;
}

export interface ProductInfo {
  name: string;
  url: string;
  n_frames: number;
  planes_per_frame: number;
  has_flags: boolean;
  bytes: number;
}

export interface CitationEntry {
  label: string;
  doi?: string | null;
  url?: string | null;
  text: string;
}

export interface SessionManifest {
  session_id: string;
  source: "preset" | "live";
  target: TargetRef;
  grid: GridSpec;
  passes: SurveyPass[];
  products: Record<string, ProductInfo>;
  frames: Record<string, FrameMeta[]>;
  warnings: string[];
  citations: CitationEntry[];
  created_utc: string;
  pipeline_version: string;
  category?: string;
  region_label?: string;
  sensors_used?: string[];
  story_scenes?: StoryScene[];
  illusion_summary?: string;
  causal_summary?: string;
  event_dates?: string[];
  geo_features?: GeoFeatureOverlay[];
}

export interface SpectrumPoint {
  wavelength_um: number;
  flux_mjysr: number;
  err: number;
  detector: number;
  mjd: number;
  obs_id: string;
  flagged: boolean;
}

export interface SpectrumResult {
  ra: number;
  dec: number;
  lon?: number;
  lat?: number;
  points: SpectrumPoint[];
  series?: Record<string, number[]>;
  dates?: string[];
  units?: Record<string, string>;
  location_story?: string;
  aperture_arcsec: number;
  n_used: number;
  n_rejected: number;
  note?: string | null;
}

export interface EonetEvent {
  id: string;
  title: string;
  category: string;
  coordinates: [number, number]; // [lon, lat]
  date: string;
  description?: string | null;
  magnitude?: string | null;
  link?: string | null;
  sources?: string[];
}

export interface GaiaSource {
  source_id: string;
  ra: number;
  dec: number;
  g_mag?: number | null;
  pmra?: number | null;
  pmdec?: number | null;
  ra_at_mjd: number;
  dec_at_mjd: number;
}

export interface AllwiseSource {
  designation: string;
  ra: number;
  dec: number;
  w1?: number | null;
  w2?: number | null;
}

export interface OverlaySet {
  gaia: GaiaSource[];
  allwise: AllwiseSource[];
  source: OverlaySource;
  mjd_ref: number;
  note?: string | null;
}

export interface ProgressEvent {
  stage: "resolve" | "query" | "plan" | "fetch" | "process" | "done" | "error";
  message: string;
  done: number;
  total: number;
  session_id?: string | null;
  error_code?: string | null;
}

export interface HealthStatus {
  irsa_ok: boolean;
  cache_entries: number;
  presets_ready: string[];
  version: string;
}

export interface PatternCandidate {
  id: string;
  kind: PatternKind;
  title: string;
  summary: string;
  confidence: "High" | "Medium";
  snr: number;
  ra: number;
  dec: number;
  fits_x: number;
  fits_y: number;
  past_fits_x?: number | null;
  past_fits_y?: number | null;
  suggested_label: string;
  metrics: Record<string, number | string>;
}

export interface PatternReport {
  session_id: string;
  n_patterns: number;
  summary: string;
  past_label?: string | null;
  present_label?: string | null;
  candidates: PatternCandidate[];
}

export interface AiExplainRequest {
  session_id?: string | null;
  question?: string;
  scene_index?: number;
  lat?: number | null;
  lon?: number | null;
  illusion_guard?: boolean;
}

export interface AiExplainResponse {
  answer: string;
  mode: "causal_graph" | "gemini_enhanced";
  recommended_layers: SignalId[];
  key_connections: string[];
  lead_lag_summary: string;
}
