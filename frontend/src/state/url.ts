import type { LensId } from "../api/types";

export interface UrlParamsState {
  mode?: "missions" | "explorer";
  mission?: string;
  ra?: string;
  dec?: string;
  fov?: number;
  lens?: LensId;
}

const VALID_LENSES = new Set<LensId>(["blink", "motion", "coldglow", "variable", "rgb", "visits"]);

export function readUrlState(): UrlParamsState {
  if (typeof window === "undefined") return {};
  const q = new URLSearchParams(window.location.search);
  const ra = q.get("ra")?.trim() || undefined;
  const dec = q.get("dec")?.trim() || undefined;
  const fovRaw = Number(q.get("fov"));
  const fov = Number.isFinite(fovRaw) && fovRaw > 0 ? fovRaw : undefined;
  const lensRaw = q.get("lens") as LensId | null;
  const lens = lensRaw && VALID_LENSES.has(lensRaw) ? lensRaw : undefined;
  const mission = q.get("mission")?.trim() || undefined;
  const modeParam = q.get("mode");
  const mode =
    modeParam === "explorer" || (ra && dec && !mission)
      ? "explorer"
      : modeParam === "missions" || mission
      ? "missions"
      : undefined;

  return { mode, mission, ra, dec, fov, lens };
}

export function writeUrlState(next: UrlParamsState): void {
  if (typeof window === "undefined") return;
  const q = new URLSearchParams();
  if (next.mode === "explorer") {
    q.set("mode", "explorer");
    if (next.ra) q.set("ra", next.ra);
    if (next.dec) q.set("dec", next.dec);
    if (next.fov) q.set("fov", String(next.fov));
  } else if (next.mission) {
    q.set("mission", next.mission);
  }
  if (next.lens) q.set("lens", next.lens);
  const query = q.toString();
  const targetUrl = query ? `${window.location.pathname}?${query}` : window.location.pathname;
  window.history.replaceState(null, "", targetUrl);
}
