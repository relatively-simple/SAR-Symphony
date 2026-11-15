export type TrainingPhase = "round1-demo" | "round2-test1" | "round2-test2" | "solo";

export const TRAINING_STORAGE_KEY_V2 = "kkn_training_v2";

export const TRAINING_DEMO_SLUG = "barnards-star";
export const SOLO_PRIMARY_SLUGS = ["eps-indi-b", "r-draconis"] as const;
export const TRAINING_USED_SLUGS = ["barnards-star", "wise-0855", "rw-aurigae"] as const;

export interface TrainingTestSpec {
  phase: "round2-test1" | "round2-test2";
  slug: string;
  targetName: string;
  testNumber: 1 | 2;
  targetX: number;
  targetY: number;
  tolerancePx: number;
  expectedKind: "cold_ir" | "variable";
  expectedLabel: string;
  prompt: string;
  action1Label: string;
  action2Label: string;
  action3Label: string;
  wrongHint: Record<string, string>;
  successNote: string;
}

export const TRAINING_TESTS: Record<"round2-test1" | "round2-test2", TrainingTestSpec> = {
  "round2-test1": {
    phase: "round2-test1",
    slug: "wise-0855",
    targetName: "WISE 0855",
    testNumber: 1,
    targetX: 14,
    targetY: 14,
    tolerancePx: 4.5,
    expectedKind: "cold_ir",
    expectedLabel: "Cold Heat World",
    prompt:
      "Your turn (Check 1 of 2): Inspect this sky patch across wavelengths. Cold ~250 K brown dwarfs disappear in short starlight — test the right lens, click the source near the dashed center circle, and classify what it is.",
    action1Label: "1. Switch to Cold Glow (3.8–5.0 µm) to look for cold heat emission",
    action2Label: "2. Click near the dashed center circle in Cold Glow to inspect its 4.5 µm spectrum",
    action3Label: "3. Classify what you see in this sky patch",
    wrongHint: {
      mover:
        "Check if a Cyan 'before' blob shifted away from a Red 'now' blob here — no strong paired shift stands out. Look at how bright the central object became only after switching to Cold Glow (4.5 µm)!",
      variable:
        "Look at its spectrum and wavelength jump: the source was nearly invisible in shorter optical/NIR light but shines strongly at 4.1–4.7 µm. What fits an invisible-until-4.5 µm object?",
      artifact:
        "Notice this glow repeats solidly right inside the center target region across SPHEREx passes and rises steeply toward 4–5 µm — that's a real ultra-cold thermal source, not a glitch.",
    },
    successNote:
      "Nailed it! You spotted WISE 0855 — one of the coldest known ~250 K rogue/brown dwarf worlds, hiding until inspected at ~4.5 µm (+50 pts).",
  },
  "round2-test2": {
    phase: "round2-test2",
    slug: "rw-aurigae",
    targetName: "RW Aurigae",
    testNumber: 2,
    targetX: 14,
    targetY: 14,
    tolerancePx: 4.5,
    expectedKind: "variable",
    expectedLabel: "Flickering Star",
    prompt:
      "Final Check (2 of 2): Compare Past vs Present here. Does the bright star at center move across sky pixels like Barnard's Star, OR stay in place and change brightness?",
    action1Label: "1. Switch to Variable Watch or Difference Only (or click Animate Blink) to compare brightness over time",
    action2Label: "2. Click the central bright star in the viewer to inspect its spectrum & light curve",
    action3Label: "3. Classify whether this star moved, flickered, or is a glitch",
    wrongHint: {
      mover:
        "Look carefully: a Moving World leaves two side-by-side spots (Cyan 'before' + Red 'now' shifted apart). Here the bright object stayed fixed at coordinate (14, 14) while changing brightness (+132% in D6)!",
      cold_ir:
        "Unlike WISE 0855, this star shines brilliantly in ALL short & long infrared wavelengths right in place while changing brightness between passes.",
      artifact:
        "Look at the Center Brightness Sparkline on the right and clean smooth dust-disk spectrum — this is a real dusty young binary star pulsating/eclipsing over months!",
    },
    successNote:
      "Training Passed! You proved you can distinguish a fixed brightening/dimming star (RW Aurigae) from a Moving World and a Cold ~4.5 µm World (+50 pts). Solo Discovery Missions unlocked!",
  },
};

export interface AutoDemoScriptStep {
  step: 0 | 1 | 2 | 3;
  title: string;
  narration: string;
  spotlight: "compare" | "diff" | "spectrum" | "verdict";
}

export const AUTO_DEMO_STEPS: AutoDemoScriptStep[] = [
  {
    step: 0,
    title: "1. Compare Past vs Present",
    narration:
      "Watch automatically on real Example #1 (Barnard's Star): 1. PAST (2025) and 2. PRESENT (2026) freeze distant background stars in place — while one bright nearby star shifts northward.",
    spotlight: "compare",
  },
  {
    step: 1,
    title: "2. Subtract to Difference Only",
    narration:
      "Switching automatically to Difference Only: stationary stars erase completely to black! Only things that moved (Cyan 'before' + Red 'now' pair) or flickered remain visible.",
    spotlight: "diff",
  },
  {
    step: 2,
    title: "3. Inspect Infrared Spectrum",
    narration:
      "Clicking directly on the moving dipole plots Barnard's Star's calibrated 0.75–5.0 µm SPHEREx infrared spectrum on the right — confirming a real cool red dwarf.",
    spotlight: "spectrum",
  },
  {
    step: 3,
    title: "4. Classify & Score Discovery Points",
    narration:
      "Red 'now' north of Cyan 'before' = Moving World! Auto-logging demo credit (+25 pts). Now press Start Round 2 below to prove you can spot the next 2 real examples yourself!",
    spotlight: "verdict",
  },
];
