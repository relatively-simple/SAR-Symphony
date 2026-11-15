import type { LensId } from "../api/types";

export interface UrlParamsState {
  mode?: "missions" | "explorer";
  mission?: string;
  ra?: string;
  dec?: string;
  fov?: number;
  lens?: LensId;
  scene?: number;
}

export function readUrlState(): UrlParamsState {
  if (typeof window === "undefined") return {};
  const params = new URLSearchParams(window.location.search);
  const modeRaw = params.get("mode");
  const mode = modeRaw === "explorer" || modeRaw === "missions" ? modeRaw : undefined;
  const mission = params.get("mission") ?? undefined;
  const ra = params.get("ra") ?? undefined;
  const dec = params.get("dec") ?? undefined;
  const fovRaw = params.get("fov");
  const fov = fovRaw ? Number(fovRaw) : undefined;
  const lensRaw = params.get("lens") as LensId | null;
  const lens = lensRaw ?? undefined;
  const sceneRaw = params.get("scene");
  const scene = sceneRaw !== null && Number.isFinite(Number(sceneRaw)) ? Number(sceneRaw) : undefined;
  return {
    mode,
    mission,
    ra,
    dec,
    fov: fov && Number.isFinite(fov) ? fov : undefined,
    lens,
    scene,
  };
}

export function writeUrlState(next: UrlParamsState): void {
  if (typeof window === "undefined") return;
  const params = new URLSearchParams();
  if (next.mode) params.set("mode", next.mode);
  if (next.mission) params.set("mission", next.mission);
  if (next.ra) params.set("ra", next.ra);
  if (next.dec) params.set("dec", next.dec);
  if (next.fov !== undefined) params.set("fov", String(next.fov));
  if (next.lens) params.set("lens", next.lens);
  if (next.scene !== undefined) params.set("scene", String(next.scene));
  const qs = params.toString();
  const nextUrl = qs ? `${window.location.pathname}?${qs}` : window.location.pathname;
  window.history.replaceState(null, "", nextUrl);
}
