export interface DecodedFramepack {
  npix: number;
  nFrames: number;
  planesPerFrame: number;
  hasFlags: boolean;
  frameIds: string[];
  data: Float32Array;
  flags: Uint16Array | null;
}

/** Decode SFP1 binary packet matching backend/app/io/framepack.py verbatim. */
export function decodeFramepack(buf: ArrayBuffer): DecodedFramepack {
  const bytes = new Uint8Array(buf);
  if (
    bytes.length < 8 ||
    bytes[0] !== 0x53 || // S
    bytes[1] !== 0x46 || // F
    bytes[2] !== 0x50 || // P
    bytes[3] !== 0x31    // 1
  ) {
    throw new Error("Invalid SFP1 frame bundle header");
  }

  const view = new DataView(buf);
  const headerLen = view.getUint32(4, true);
  const headerEnd = 8 + headerLen;
  const headerJson = new TextDecoder("utf-8").decode(bytes.subarray(8, headerEnd));
  const header = JSON.parse(headerJson) as {
    npix: number;
    n_frames: number;
    planes_per_frame: number;
    has_flags: boolean;
    frame_ids: string[];
  };

  const padLen = (4 - (headerEnd % 4)) % 4;
  const dataOffset = headerEnd + padLen;
  const floatCount = header.n_frames * header.planes_per_frame * header.npix * header.npix;
  const data = new Float32Array(buf, dataOffset, floatCount);

  let flags: Uint16Array | null = null;
  if (header.has_flags) {
    const flagsOffset = dataOffset + floatCount * 4;
    const flagCount = header.n_frames * header.npix * header.npix;
    flags = new Uint16Array(buf, flagsOffset, flagCount);
  }

  return {
    npix: header.npix,
    nFrames: header.n_frames,
    planesPerFrame: header.planes_per_frame,
    hasFlags: header.has_flags,
    frameIds: header.frame_ids,
    data,
    flags,
  };
}
