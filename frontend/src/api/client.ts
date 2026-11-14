import type {
  HealthStatus,
  OverlaySet,
  SessionManifest,
  SpectrumResult,
  TargetPreset,
} from "./types";

async function readJson<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let msg = `HTTP ${res.status}`;
    try {
      const err = await res.json();
      msg = err.message || err.detail || msg;
    } catch {
      // ignore non-JSON body
    }
    throw new Error(msg);
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
    throw new Error(`Failed loading frame bundle (${res.status})`);
  }
  return res.arrayBuffer();
}

export async function fetchSpectrum(
  sessionId: string,
  ra: number,
  dec: number
): Promise<SpectrumResult> {
  const q = new URLSearchParams({ ra: String(ra), dec: String(dec) });
  return readJson(await fetch(`/api/sessions/${encodeURIComponent(sessionId)}/spectrum?${q}`));
}

export async function fetchOverlays(
  ra: number,
  dec: number,
  fov: number,
  mjd: number,
  preset?: string | null
): Promise<OverlaySet> {
  const q = new URLSearchParams({
    ra: String(ra),
    dec: String(dec),
    fov: String(fov),
    mjd: String(mjd),
  });
  if (preset) q.set("preset", preset);
  return readJson(await fetch(`/api/overlays?${q}`));
}

export async function fetchHealth(): Promise<HealthStatus> {
  return readJson(await fetch("/api/health"));
}
