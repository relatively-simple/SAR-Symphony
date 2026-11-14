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
}

const _offscreen = document.createElement("canvas");
const _offscreenCtx = _offscreen.getContext("2d");
let _cachedImgData: ImageData | null = null;
let _cachedNpix = 0;

function getReusableImageData(ctx: CanvasRenderingContext2D, npix: number): ImageData {
  if (_cachedImgData && _cachedNpix === npix) {
    return _cachedImgData;
  }
  _cachedImgData = ctx.createImageData(npix, npix);
  _cachedNpix = npix;
  return _cachedImgData;
}

/** Draw one frame cleanly (North-Up, East-Left) into destination canvas using smooth scaling. */
export function renderFrameToCanvas(
  canvas: HTMLCanvasElement,
  pack: DecodedFramepack,
  frameIndex: number,
  opts: RenderOptions
): void {
  const { npix, planesPerFrame, data, flags } = pack;
  if (npix <= 0 || frameIndex < 0 || frameIndex >= pack.nFrames || !_offscreenCtx) return;

  if (_offscreen.width !== npix || _offscreen.height !== npix) {
    _offscreen.width = npix;
    _offscreen.height = npix;
  }

  const imgData = getReusableImageData(_offscreenCtx, npix);
  const out = imgData.data;
  const planeStride = npix * npix;
  const frameStride = planesPerFrame * planeStride;
  const base = frameIndex * frameStride;
  const fBase = frameIndex * planeStride;

  const { stretchFn, lo, hi, diverging, showFlags } = opts;
  const divPalette = opts.palette === "orange-blue" ? "orange-blue" : "red-cyan";
  const seqPalette = opts.palette === "inferno" ? "inferno" : "grey";

  for (let fy = 0; fy < npix; fy++) {
    // Flip vertically so FITS row npix-1 (North) appears at canvas top cy=0
    const cy = npix - 1 - fy;
    const rowOff = fy * npix;
    const outRowOff = cy * npix;
    for (let fx = 0; fx < npix; fx++) {
      const fIdx = rowOff + fx;
      const pIdx = (outRowOff + fx) * 4;

      let r = 10;
      let g = 14;
      let b = 24;

      if (planesPerFrame === 3) {
        const vr = data[base + fIdx];
        const vg = data[base + planeStride + fIdx];
        const vb = data[base + 2 * planeStride + fIdx];
        if (Number.isFinite(vr) || Number.isFinite(vg) || Number.isFinite(vb)) {
          r = Number.isFinite(vr) ? Math.round(stretchPositive(vr, stretchFn, lo, hi) * 255) : 0;
          g = Number.isFinite(vg) ? Math.round(stretchPositive(vg, stretchFn, lo, hi) * 255) : 0;
          b = Number.isFinite(vb) ? Math.round(stretchPositive(vb, stretchFn, lo, hi) * 255) : 0;
        } else {
          r = 12; g = 16; b = 28;
        }
      } else {
        const val = data[base + fIdx];
        if (!Number.isFinite(val)) {
          const chk = (fx + cy) % 2 === 0 ? 18 : 13;
          r = chk; g = chk + 3; b = chk + 12;
        } else if (diverging) {
          const s = stretchDiverging(val, stretchFn, lo, hi);
          [r, g, b] = sampleDiverging(s, divPalette);
        } else {
          const u = stretchPositive(val, stretchFn, lo, hi);
          [r, g, b] = sampleSequential(u, seqPalette);
        }
      }

      if (showFlags && flags) {
        const flg = flags[fBase + fIdx];
        if ((flg & 0b101110) !== 0) {
          r = Math.min(255, Math.round(r * 0.55 + 115));
          g = Math.round(g * 0.45);
          b = Math.min(255, Math.round(b * 0.55 + 75));
        } else if ((flg & 0b010001) !== 0) {
          g = Math.min(255, Math.round(g * 0.6 + 100));
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
  ctx.imageSmoothingEnabled = true;
  ctx.imageSmoothingQuality = "high";
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  ctx.drawImage(_offscreen, 0, 0, canvas.width, canvas.height);
}
