import type { StretchFn } from "../api/types";
import type { DecodedFramepack } from "./framepack";
import { sampleDiverging, sampleSequential } from "./colormaps";
import { stretchDiverging, stretchPositive } from "./stretch";

export interface RenderOptions {
  stretchFn: StretchFn;
  lo: number;
  hi: number;
  diverging: boolean;
  palette: "grey" | "inferno" | "red-cyan" | "orange-blue";
  showFlags: boolean;
  autoRange?: boolean;
  cleanMode?: boolean;
  crispPixels?: boolean;
}

interface PlaneStats {
  med: number;
  sigma: number;
  p995: number;
  abs995: number;
}

const _offscreen = document.createElement("canvas");
const _offscreenCtx = _offscreen.getContext("2d");
let _cachedImgData: ImageData | null = null;
let _cachedNpix = 0;
const _statsCache = new WeakMap<Float32Array, Map<number, PlaneStats>>();

function getReusableImageData(ctx: CanvasRenderingContext2D, npix: number): ImageData {
  if (_cachedImgData && _cachedNpix === npix) {
    return _cachedImgData;
  }
  _cachedImgData = ctx.createImageData(npix, npix);
  _cachedNpix = npix;
  return _cachedImgData;
}

function getPlaneStats(data: Float32Array, offset: number, count: number): PlaneStats {
  let map = _statsCache.get(data);
  if (!map) {
    map = new Map<number, PlaneStats>();
    _statsCache.set(data, map);
  }
  const hit = map.get(offset);
  if (hit) return hit;

  const vals: number[] = [];
  for (let i = 0; i < count; i++) {
    const v = data[offset + i];
    if (Number.isFinite(v)) vals.push(v);
  }
  if (vals.length === 0) {
    const empty: PlaneStats = { med: 0, sigma: 1, p995: 1, abs995: 1 };
    map.set(offset, empty);
    return empty;
  }
  vals.sort((a, b) => a - b);
  const n = vals.length;
  const med = vals[Math.floor(n / 2)];
  const p995 = vals[Math.min(n - 1, Math.floor(n * 0.995))];

  const absDev = new Float32Array(n);
  for (let i = 0; i < n; i++) {
    absDev[i] = Math.abs(vals[i] - med);
  }
  absDev.sort();
  const mad = absDev[Math.floor(n / 2)];
  const sigma = Math.max(1.4826 * mad, 1e-6);
  const abs995 = Math.max(absDev[Math.min(n - 1, Math.floor(n * 0.995))], 6.0 * sigma);

  const stats: PlaneStats = { med, sigma, p995, abs995 };
  map.set(offset, stats);
  return stats;
}

/** Draw one 2D float32 plane cleanly (North-Up, East-Left) into destination canvas. */
export function renderPlaneToCanvas(
  canvas: HTMLCanvasElement,
  npix: number,
  data: Float32Array,
  dataOffset: number,
  flags: Uint16Array | null,
  flagsOffset: number,
  opts: RenderOptions
): void {
  if (npix <= 0 || !_offscreenCtx) return;

  if (_offscreen.width !== npix || _offscreen.height !== npix) {
    _offscreen.width = npix;
    _offscreen.height = npix;
  }

  const imgData = getReusableImageData(_offscreenCtx, npix);
  const out = imgData.data;
  const planeStride = npix * npix;

  const {
    stretchFn,
    lo,
    hi,
    diverging,
    showFlags,
    autoRange = true,
    cleanMode = true,
    crispPixels = true,
  } = opts;
  const divPalette = opts.palette === "orange-blue" ? "orange-blue" : "red-cyan";
  const seqPalette = opts.palette === "inferno" ? "inferno" : "grey";

  const stats = autoRange ? getPlaneStats(data, dataOffset, planeStride) : null;
  const bgMed = stats ? stats.med : 0;
  const sigma = stats ? stats.sigma : 1;
  const diffGate = cleanMode && diverging && stats ? 2.3 * sigma : 0;
  const diffScale = stats
    ? Math.max(stats.abs995 - diffGate, 7.0 * sigma, Math.abs(lo), Math.abs(hi), 1e-6)
    : Math.max(Math.abs(lo), Math.abs(hi), 1e-6);

  const seqLo =
    autoRange && !diverging && stats
      ? bgMed + (cleanMode ? 1.15 * sigma : -0.2 * sigma)
      : lo;
  const seqHi =
    autoRange && !diverging && stats
      ? Math.max(stats.p995, bgMed + 6.5 * sigma, seqLo + 1e-5)
      : hi;

  // Detect NaN pixels inside bright star cores (coadd clears OVERFLOW when weights==0)
  const coreThresh = 5.0 * sigma;
  const hasBrightHaloNeighbors = (cx: number, cy: number): boolean => {
    let hits = 0;
    const y0 = Math.max(0, cy - 2);
    const y1 = Math.min(npix - 1, cy + 2);
    const x0 = Math.max(0, cx - 2);
    const x1 = Math.min(npix - 1, cx + 2);
    for (let ny = y0; ny <= y1; ny++) {
      const nRow = dataOffset + ny * npix;
      for (let nx = x0; nx <= x1; nx++) {
        if (nx === cx && ny === cy) continue;
        const nv = data[nRow + nx];
        if (!Number.isFinite(nv)) continue;
        const above = diverging ? Math.abs(nv - bgMed) > coreThresh : nv - bgMed > coreThresh;
        if (above) {
          hits++;
          if (hits >= 2) return true;
        }
      }
    }
    return false;
  };

  for (let fy = 0; fy < npix; fy++) {
    const cy = npix - 1 - fy;
    const rowOff = fy * npix;
    const outRowOff = cy * npix;
    for (let fx = 0; fx < npix; fx++) {
      const fIdx = rowOff + fx;
      const pIdx = (outRowOff + fx) * 4;
      const val = data[dataOffset + fIdx];
      const flg = flags ? flags[flagsOffset + fIdx] : 0;

      let r = 8;
      let g = 12;
      let b = 20;

      if (!Number.isFinite(val)) {
        const isOverflowCore = (flg & 2) !== 0 || hasBrightHaloNeighbors(fx, fy);
        if (isOverflowCore) {
          // Saturated star core renders cleanly as a glowing center instead of a dark hole
          if (diverging) {
            r = 188;
            g = 200;
            b = 218;
          } else {
            r = 236;
            g = 239;
            b = 246;
          }
        } else {
          r = 10;
          g = 14;
          b = 22;
        }
      } else if (diverging) {
        const centered = autoRange ? val - bgMed : val;
        const mag = Math.abs(centered);
        if (mag <= diffGate) {
          r = 8;
          g = 12;
          b = 20;
        } else {
          const gated = Math.sign(centered) * (mag - diffGate);
          const s = stretchDiverging(gated, stretchFn, -diffScale, diffScale);
          [r, g, b] = sampleDiverging(s, divPalette);
        }
      } else {
        const u = stretchPositive(val, stretchFn, seqLo, seqHi);
        [r, g, b] = sampleSequential(u, seqPalette);
      }

      if (showFlags && flags) {
        if ((flg & 0b101110) !== 0) {
          r = Math.min(255, Math.round(r * 0.55 + 110));
          g = Math.round(g * 0.45);
          b = Math.min(255, Math.round(b * 0.55 + 75));
        } else if ((flg & 0b010001) !== 0) {
          g = Math.min(255, Math.round(g * 0.6 + 95));
          b = Math.min(255, Math.round(b * 0.7 + 45));
        }
      }

      out[pIdx] = r;
      out[pIdx + 1] = g;
      out[pIdx + 2] = b;
      out[pIdx + 3] = 255;
    }
  }

  _offscreenCtx.putImageData(imgData, 0, 0);

  const ctx = canvas.getContext("2d");
  if (!ctx) return;
  ctx.imageSmoothingEnabled = !crispPixels;
  if (!crispPixels) {
    ctx.imageSmoothingQuality = "high";
  }
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  ctx.drawImage(_offscreen, 0, 0, canvas.width, canvas.height);
}

/** Draw one frame from a DecodedFramepack cleanly (supports both 1-plane and RGB 3-plane cubes). */
export function renderFrameToCanvas(
  canvas: HTMLCanvasElement,
  pack: DecodedFramepack,
  frameIndex: number,
  opts: RenderOptions
): void {
  const { npix, planesPerFrame, data, flags } = pack;
  if (npix <= 0 || frameIndex < 0 || frameIndex >= pack.nFrames || !_offscreenCtx) return;

  const planeStride = npix * npix;
  const frameStride = planesPerFrame * planeStride;
  const base = frameIndex * frameStride;
  const fBase = frameIndex * planeStride;

  if (planesPerFrame !== 3) {
    renderPlaneToCanvas(canvas, npix, data, base, flags, fBase, opts);
    return;
  }

  if (_offscreen.width !== npix || _offscreen.height !== npix) {
    _offscreen.width = npix;
    _offscreen.height = npix;
  }

  const imgData = getReusableImageData(_offscreenCtx, npix);
  const out = imgData.data;
  const { stretchFn, lo, hi, showFlags, crispPixels = true } = opts;

  for (let fy = 0; fy < npix; fy++) {
    const cy = npix - 1 - fy;
    const rowOff = fy * npix;
    const outRowOff = cy * npix;
    for (let fx = 0; fx < npix; fx++) {
      const fIdx = rowOff + fx;
      const pIdx = (outRowOff + fx) * 4;
      const vr = data[base + fIdx];
      const vg = data[base + planeStride + fIdx];
      const vb = data[base + 2 * planeStride + fIdx];

      let r = 8;
      let g = 12;
      let b = 20;
      if (Number.isFinite(vr) || Number.isFinite(vg) || Number.isFinite(vb)) {
        r = Number.isFinite(vr) ? Math.round(stretchPositive(vr, stretchFn, lo, hi) * 255) : 0;
        g = Number.isFinite(vg) ? Math.round(stretchPositive(vg, stretchFn, lo, hi) * 255) : 0;
        b = Number.isFinite(vb) ? Math.round(stretchPositive(vb, stretchFn, lo, hi) * 255) : 0;
      } else if (flags && (flags[fBase + fIdx] & 2) !== 0) {
        r = 226; g = 232; b = 244;
      }

      if (showFlags && flags) {
        const flg = flags[fBase + fIdx];
        if ((flg & 0b101110) !== 0) {
          r = Math.min(255, Math.round(r * 0.55 + 110));
          g = Math.round(g * 0.45);
          b = Math.min(255, Math.round(b * 0.55 + 75));
        }
      }

      out[pIdx] = r;
      out[pIdx + 1] = g;
      out[pIdx + 2] = b;
      out[pIdx + 3] = 255;
    }
  }

  _offscreenCtx.putImageData(imgData, 0, 0);
  const ctx = canvas.getContext("2d");
  if (!ctx) return;
  ctx.imageSmoothingEnabled = !crispPixels;
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  ctx.drawImage(_offscreen, 0, 0, canvas.width, canvas.height);
}
