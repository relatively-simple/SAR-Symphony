import type {
  AiExplainRequest,
  AiExplainResponse,
  EonetEvent,
  HealthStatus,
  OverlaySet,
  PatternReport,
  SessionManifest,
  SpectrumResult,
  TargetPreset,
} from "./types";

async function readJson<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const errBody = await res.json();
      if (errBody && typeof errBody.message === "string") {
        detail = errBody.message;
      } else if (errBody && typeof errBody.detail === "string") {
        detail = errBody.detail;
      }
    } catch {
      // keep status string
    }
    throw new Error(detail);
  }
  return res.json() as Promise<T>;
}

export async function fetchTargets(): Promise<TargetPreset[]> {
  return readJson(await fetch("/api/targets"));
}

export async function fetchTargetSession(slug: string): Promise<SessionManifest> {
  return readJson(await fetch(`/api/targets/${encodeURIComponent(slug)}`));
}

export async function fetchSession(sessionId: string): Promise<SessionManifest> {
  return readJson(await fetch(`/api/sessions/${encodeURIComponent(sessionId)}`));
}

export async function fetchFramepackBuffer(url: string): Promise<ArrayBuffer> {
  const res = await fetch(url);
  if (!res.ok) {
    throw new Error(`Failed loading framepack ${url} (HTTP ${res.status})`);
  }
  return res.arrayBuffer();
}

export async function fetchSpectrum(
  sessionId: string,
  lon: number,
  lat: number,
  radiusArcsec = 6.0
): Promise<SpectrumResult> {
  const q = new URLSearchParams({
    ra: String(lon),
    dec: String(lat),
    radius_arcsec: String(radiusArcsec),
  });
  return readJson(await fetch(`/api/sessions/${encodeURIComponent(sessionId)}/spectrum?${q}`));
}

export async function fetchOverlays(
  lon: number,
  lat: number,
  fov: number,
  mjd: number,
  preset?: string | null
): Promise<OverlaySet> {
  const q = new URLSearchParams({
    ra: String(lon),
    dec: String(lat),
    fov: String(fov),
    mjd: String(mjd),
  });
  if (preset) q.set("preset", preset);
  return readJson(await fetch(`/api/overlays?${q}`));
}

export async function fetchHealth(): Promise<HealthStatus> {
  return readJson(await fetch("/api/health"));
}

export async function fetchPatterns(sessionId: string): Promise<PatternReport> {
  return readJson(await fetch(`/api/sessions/${encodeURIComponent(sessionId)}/patterns`));
}

export async function fetchEonet(category?: string, limit = 20): Promise<EonetEvent[]> {
  const q = new URLSearchParams({ limit: String(limit) });
  if (category) q.set("category", category);
  const queryStr = `?${q}`;
  return readJson(await fetch(`/api/eonet${queryStr}`));
}

export interface LiveStoryParams {
  q?: string;
  lat?: number;
  lon?: number;
  title?: string;
  category?: string;
  fov?: number;
}

export async function fetchLiveStory(params: LiveStoryParams): Promise<SessionManifest> {
  const q = new URLSearchParams();
  if (params.q) q.set("q", params.q);
  if (params.lat !== undefined) q.set("lat", String(params.lat));
  if (params.lon !== undefined) q.set("lon", String(params.lon));
  if (params.title) q.set("title", params.title);
  if (params.category) q.set("category", params.category);
  if (params.fov !== undefined) q.set("fov", String(params.fov));
  return readJson(await fetch(`/api/story/live?${q}`));
}

export async function fetchAiExplain(req: AiExplainRequest): Promise<AiExplainResponse> {
  return readJson(
    await fetch("/api/ai/explain", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(req),
    })
  );
}
