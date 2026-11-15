export type ColormapKind = "grey" | "inferno" | "red-cyan" | "orange-blue";

export function sampleSequential(u: number, kind: "grey" | "inferno"): [number, number, number] {
  const t = Math.max(0, Math.min(1, u));
  if (kind === "grey") {
    const c = Math.round(8 + t * 247);
    return [c, c, Math.min(255, c + 4)];
  }
  if (t <= 0.004) {
    return [7, 10, 18];
  }
  // Obsidian night floor -> Deep Violet -> Bright Amber -> Starlight Gold-White
  const r = Math.round(Math.min(255, 7 + 248 * Math.pow(t, 0.85)));
  const g = Math.round(Math.min(255, 10 + 232 * Math.pow(t, 1.38)));
  const b = Math.round(Math.min(255, 18 + 225 * Math.pow(t, 2.25)));
  return [r, g, b];
}

export function sampleDiverging(
  s: number,
  palette: "red-cyan" | "orange-blue"
): [number, number, number] {
  const x = Math.max(-1, Math.min(1, s));
  if (Math.abs(x) <= 0.004) {
    return [8, 12, 20];
  }
  const m = Math.pow(Math.abs(x), 0.86);
  if (palette === "orange-blue") {
    if (x >= 0) {
      return [
        Math.round(10 + 245 * m),
        Math.round(14 + 145 * m),
        Math.round(24 * (1 - m)),
      ];
    }
    return [
      Math.round(10 * (1 - m)),
      Math.round(14 + 165 * m),
      Math.round(24 + 231 * m),
    ];
  }
  // Crisp Neon Coral-Red ('Now / +') vs Electric Cyan ('Before / -') over pitch obsidian
  if (x >= 0) {
    return [
      Math.round(12 + 243 * m),
      Math.round(16 + 72 * m * m),
      Math.round(24 + 78 * m),
    ];
  }
  return [
    Math.round(12 + 20 * m),
    Math.round(16 + 212 * m),
    Math.round(24 + 231 * m),
  ];
}
