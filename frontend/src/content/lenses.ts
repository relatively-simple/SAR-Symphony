import type { LensId } from "../api/types";

export interface LensSpec {
  id: LensId;
  productKey: "diffs" | "coldglow" | "pass_coadds" | "rgb" | "visits";
  label: string;
  shortName: string;
  badge: string;
  palette: "red-cyan" | "orange-blue" | "inferno" | "grey";
  diverging: boolean;
  howToRead: string;
  legendLeft: string;
  legendRight: string;
  isProOnly?: boolean;
}

export const LENS_SPECS: Record<LensId, LensSpec> = {
  motion: {
    id: "motion",
    productKey: "diffs",
    label: "Motion Finder",
    shortName: "Motion",
    badge: "Pass_n - Pass_0",
    palette: "red-cyan",
    diverging: true,
    howToRead:
      "Fixed background stars subtract cleanly to neutral slate. Any star or brown dwarf that moved between Survey Pass 0 and Pass n leaves a bright RED 'now' spot paired with a CYAN 'then' shadow.",
    legendLeft: "- Flux (Was here in Pass 0)",
    legendRight: "+ Flux (Moved here now)",
  },
  coldglow: {
    id: "coldglow",
    productKey: "coldglow",
    label: "Cold Glow",
    shortName: "Cold Glow",
    badge: "D5+D6 (3.8-5.0 um)",
    palette: "inferno",
    diverging: false,
    howToRead:
      "Stacks SPHEREx's longest thermal infrared bands (Detectors D5+D6: 3.8-5.0 um) per pass. Cold ~250-900 K brown dwarfs and dusty worlds glow brightly here while vanishing in optical/short-NIR images.",
    legendLeft: "Cold sky floor",
    legendRight: "3.8-5.0 um thermal glow (MJy/sr)",
  },
  variable: {
    id: "variable",
    productKey: "pass_coadds",
    label: "Variable Watch",
    shortName: "Variable",
    badge: "Per-Pass Coadd",
    palette: "inferno",
    diverging: false,
    howToRead:
      "Calibrated brightness coadded per 6-month survey pass. Press Play to watch pulsating Mira giants, young flickering T Tauri stars, or eclipses swell and dim over time.",
    legendLeft: "Sky floor (faint)",
    legendRight: "Bright emission (MJy/sr)",
  },
  rgb: {
    id: "rgb",
    productKey: "rgb",
    label: "False-Color IR",
    shortName: "IR RGB",
    badge: "R:D5+6 G:D3+4 B:D1+2",
    palette: "grey",
    diverging: false,
    howToRead:
      "Maps SPHEREx's 0.75-5.0 um spectrum directly to RGB channels: Blue (0.75-1.6 um), Green (1.6-3.8 um), Red (3.8-5.0 um). Normal stars appear blue-white; ultra-cool brown dwarfs & embedded stars glow deep crimson-orange.",
    legendLeft: "Blue = Short NIR (D1-D2)",
    legendRight: "Red = Thermal IR (D5-D6)",
  },
  visits: {
    id: "visits",
    productKey: "visits",
    label: "Raw Exposures",
    shortName: "Raw Visits",
    badge: "Individual Level-2 Frames",
    palette: "grey",
    diverging: false,
    howToRead:
      "Inspect unstacked, north-up reprojected Level 2 single detector frames across all survey passes. Use the Detector D1-D6 filter in Pro Controls to isolate individual spectral bands.",
    legendLeft: "Background",
    legendRight: "Raw detector signal",
    isProOnly: true,
  },
};

export const PRIMARY_LENSES: LensId[] = ["motion", "coldglow", "variable", "rgb"];
