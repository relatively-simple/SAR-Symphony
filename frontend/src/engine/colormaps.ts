export type ColormapKind = "grey" | "inferno" | "red-cyan" | "orange-blue";

export function sampleSequential(u: number, kind: "grey" | "inferno"): [number, number, number] {
  const t = Math.max(0, Math.min(1, u));
  if (kind === "grey") {
    const c = Math.round(t * 255);
    return [c, c, c];
  }
  // Obsidian -> Deep Violet -> Amber -> White-Gold (Cold Glow palette)
  const r = Math.round(Math.min(255, 14 + 241 * Math.pow(t, 0.72)));
  const g = Math.round(Math.min(255, 11 + 215 * Math.pow(t, 1.38)));
  const b = Math.round(Math.min(255, 26 + 229 * Math.pow(t, 2.35)));
  return [r, g, b];
}

export function sampleDiverging(
  s: number,
  palette: "red-cyan" | "orange-blue"
): [number, number, number] {
  const x = Math.max(-1, Math.min(1, s));
  const m = Math.sqrt(Math.abs(x));
  if (palette === "orange-blue") {
    // Color-blind safe: Teal/Blue negative (old position) -> Dark Neutral -> Vivid Orange positive (new position)
    if (x >= 0) {
      return [
        Math.round(22 + 233 * m),
        Math.round(26 + 135 * m),
        Math.round(42 * (1 - m)),
      ];
    }
    return [
      Math.round(22 * (1 - m)),
      Math.round(26 + 150 * m),
      Math.round(42 + 213 * m),
    ];
  }
  // Default Crimson/Rose (+) vs Cyan (-) for crisp motion dipoles
  if (x >= 0) {
    return [
      Math.round(18 + 237 * m),
      Math.round(22 + 65 * m * m),
      Math.round(36 + 75 * m),
    ];
  }
  return [
    Math.round(18 + 18 * m),
    Math.round(22 + 205 * m),
    Math.round(36 + 219 * m),
  ];
}
