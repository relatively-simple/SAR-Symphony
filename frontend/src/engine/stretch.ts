import type { StretchFn } from "../api/types";

const ASINH_K = 6.0;
const ASINH_NORM = Math.asinh(ASINH_K);

/** Map pixel intensity `v` within [lo, hi] to [0, 1] using chosen stretch curve. */
export function stretchPositive(v: number, fn: StretchFn, lo: number, hi: number): number {
  const span = Math.max(hi - lo, 1e-9);
  const u = Math.max(0, Math.min(1, (v - lo) / span));
  if (fn === "linear") return u;
  if (fn === "log") return Math.log1p(u * 25.0) / Math.log1p(25.0);
  return Math.asinh(u * ASINH_K) / ASINH_NORM;
}

/** Map symmetric signed difference value `v` within [-scale, +scale] to [-1, 1]. */
export function stretchDiverging(v: number, fn: StretchFn, lo: number, hi: number): number {
  const absScale = Math.max(Math.abs(lo), Math.abs(hi), 1e-9);
  const s = Math.max(-1, Math.min(1, v / absScale));
  if (fn === "linear") return s;
  const mag = Math.abs(s);
  const stretched =
    fn === "log"
      ? Math.log1p(mag * 12.0) / Math.log1p(12.0)
      : Math.asinh(mag * 5.0) / Math.asinh(5.0);
  return Math.sign(s) * stretched;
}
