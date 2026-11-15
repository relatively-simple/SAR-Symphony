import type { FrameMeta, SessionManifest } from "../api/types";
import type { DecodedFramepack } from "./framepack";

export interface SimpleCompareData {
  npix: number;
  pastLabel: string;
  pastDate: string;
  pastMjd: number;
  presentLabel: string;
  presentDate: string;
  presentMjd: number;
  diffLabel: string;
  pastPlane: Float32Array;
  presentPlane: Float32Array;
  diffPlane: Float32Array;
  pastFlags: Uint16Array;
  presentFlags: Uint16Array;
  diffFlags: Uint16Array;
  blinkPack: DecodedFramepack;
  blinkMetas: FrameMeta[];
}

function normalizePlane(
  src: Float32Array,
  offset: number,
  count: number
): Float32Array {
  const vals: number[] = [];
  for (let i = 0; i < count; i++) {
    const v = src[offset + i];
    if (Number.isFinite(v)) vals.push(v);
  }
  const out = new Float32Array(count);
  if (vals.length < 4) {
    out.fill(Number.NaN);
    return out;
  }
  vals.sort((a, b) => a - b);
  const med = vals[Math.floor(vals.length / 2)];
  const dev = new Float32Array(vals.length);
  for (let i = 0; i < vals.length; i++) dev[i] = Math.abs(vals[i] - med);
  dev.sort();
  const sig = Math.max(1.4826 * dev[Math.floor(dev.length / 2)], 1e-5);
  for (let i = 0; i < count; i++) {
    const v = src[offset + i];
    out[i] = Number.isFinite(v) ? (v - med) / sig : Number.NaN;
  }
  return out;
}

function medianStackNormalized(
  pack: DecodedFramepack,
  frameIndices: number[],
  npix: number
): { plane: Float32Array; flags: Uint16Array } {
  const stride = npix * npix;
  const zPlanes = frameIndices.map((idx) =>
    normalizePlane(pack.data, idx * pack.planesPerFrame * stride, stride)
  );
  const out = new Float32Array(stride);
  const outFlags = new Uint16Array(stride);
  const buf: number[] = [];

  for (let i = 0; i < stride; i++) {
    buf.length = 0;
    let overflowVotes = 0;
    for (let j = 0; j < zPlanes.length; j++) {
      const v = zPlanes[j][i];
      if (Number.isFinite(v)) {
        buf.push(v);
      } else if (pack.flags && (pack.flags[frameIndices[j] * stride + i] & 2) !== 0) {
        overflowVotes++;
      }
    }
    if (buf.length === 0) {
      out[i] = Number.NaN;
      outFlags[i] = overflowVotes > 0 ? 2 : 32;
    } else {
      buf.sort((a, b) => a - b);
      const mid = Math.floor(buf.length / 2);
      out[i] = buf.length % 2 === 1 ? buf[mid] : 0.5 * (buf[mid - 1] + buf[mid]);
      outFlags[i] = 0;
    }
  }
  return { plane: out, flags: outFlags };
}

/** Build clean multi-band PAST, PRESENT, and DIFFERENCE ONLY maps for citizen comparison. */
export function buildSimpleCompare(
  manifest: SessionManifest | null,
  coaddPack: DecodedFramepack | null | undefined,
  diffPack: DecodedFramepack | null | undefined
): SimpleCompareData | null {
  if (!manifest || !coaddPack) return null;
  const coaddMetas = manifest.frames.pass_coadds ?? [];
  if (coaddMetas.length === 0) return null;

  const npix = manifest.grid.npix;
  const stride = npix * npix;
  const passNums = Array.from(new Set(coaddMetas.map((m) => m.pass_index))).sort((a, b) => a - b);
  const firstPass = passNums[0];
  const lastPass = passNums[passNums.length - 1];

  const pastIdx: number[] = [];
  const presentIdx: number[] = [];
  for (let i = 0; i < coaddMetas.length; i++) {
    const pIdx = coaddPack.frameIds.indexOf(coaddMetas[i].id);
    if (pIdx < 0) continue;
    if (coaddMetas[i].pass_index === firstPass) pastIdx.push(pIdx);
    if (coaddMetas[i].pass_index === lastPass) presentIdx.push(pIdx);
  }
  if (pastIdx.length === 0 || presentIdx.length === 0) return null;

  const { plane: pastPlane, flags: pastFlags } = medianStackNormalized(coaddPack, pastIdx, npix);
  const { plane: presentPlane, flags: presentFlags } = medianStackNormalized(
    coaddPack,
    presentIdx,
    npix
  );

  // Build detector-matched multi-band difference plane (cancels wavelength PSF differences cleanly)
  const diffMetas = manifest.frames.diffs ?? [];
  let diffPlane: Float32Array;
  let diffFlags: Uint16Array;

  if (diffPack && diffMetas.length > 0) {
    const maxDiffPass = Math.max(...diffMetas.map((m) => m.pass_index));
    const diffIdx: number[] = [];
    for (const dm of diffMetas) {
      if (dm.pass_index === maxDiffPass) {
        const idx = diffPack.frameIds.indexOf(dm.id);
        if (idx >= 0) diffIdx.push(idx);
      }
    }
    if (diffIdx.length > 0) {
      const stacked = medianStackNormalized(diffPack, diffIdx, npix);
      diffPlane = stacked.plane;
      diffFlags = stacked.flags;
    } else {
      diffPlane = new Float32Array(stride);
      diffFlags = new Uint16Array(stride);
      for (let i = 0; i < stride; i++) {
        diffPlane[i] = presentPlane[i] - pastPlane[i];
        diffFlags[i] = pastFlags[i] | presentFlags[i];
      }
    }
  } else {
    diffPlane = new Float32Array(stride);
    diffFlags = new Uint16Array(stride);
    for (let i = 0; i < stride; i++) {
      diffPlane[i] = presentPlane[i] - pastPlane[i];
      diffFlags[i] = pastFlags[i] | presentFlags[i];
    }
  }

  const pastMetaSrc = coaddMetas.find((m) => m.pass_index === firstPass) ?? coaddMetas[0];
  const presentMetaSrc =
    coaddMetas.find((m) => m.pass_index === lastPass) ?? coaddMetas[coaddMetas.length - 1];

  const blinkData = new Float32Array(2 * stride);
  blinkData.set(pastPlane, 0);
  blinkData.set(presentPlane, stride);

  const blinkFlags = new Uint16Array(2 * stride);
  blinkFlags.set(pastFlags, 0);
  blinkFlags.set(presentFlags, stride);

  const blinkPack: DecodedFramepack = {
    npix,
    nFrames: 2,
    planesPerFrame: 1,
    hasFlags: true,
    frameIds: ["simple_past", "simple_present"],
    data: blinkData,
    flags: blinkFlags,
  };

  const blinkMetas: FrameMeta[] = [
    {
      id: "simple_past",
      kind: "coadd",
      pass_index: firstPass,
      pass_label: `PAST · ${pastMetaSrc.pass_label}`,
      detector: null,
      mjd: pastMetaSrc.mjd,
      date_utc: pastMetaSrc.date_utc,
      wavelength_um: null,
      obs_ids: pastMetaSrc.obs_ids,
      flag_summary: {},
      n_inputs: pastIdx.length,
      stretch_hint: { p_lo: 0.5, p_hi: 25.0 },
    },
    {
      id: "simple_present",
      kind: "coadd",
      pass_index: lastPass,
      pass_label: `PRESENT · ${presentMetaSrc.pass_label}`,
      detector: null,
      mjd: presentMetaSrc.mjd,
      date_utc: presentMetaSrc.date_utc,
      wavelength_um: null,
      obs_ids: presentMetaSrc.obs_ids,
      flag_summary: {},
      n_inputs: presentIdx.length,
      stretch_hint: { p_lo: 0.5, p_hi: 25.0 },
    },
  ];

  return {
    npix,
    pastLabel: `PAST (${pastMetaSrc.pass_label})`,
    pastDate: pastMetaSrc.date_utc.split(" ")[0],
    pastMjd: pastMetaSrc.mjd,
    presentLabel: `PRESENT (${presentMetaSrc.pass_label})`,
    presentDate: presentMetaSrc.date_utc.split(" ")[0],
    presentMjd: presentMetaSrc.mjd,
    diffLabel: `DIFFERENCE (${presentMetaSrc.pass_label} - ${pastMetaSrc.pass_label})`,
    pastPlane,
    presentPlane,
    diffPlane,
    pastFlags,
    presentFlags,
    diffFlags,
    blinkPack,
    blinkMetas,
  };
}
