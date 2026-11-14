export interface GlossaryEntry {
  id: string;
  term: string;
  shortLabel: string;
  definition: string;
  whyItMatters: string;
}

export const GLOSSARY_ENTRIES: GlossaryEntry[] = [
  {
    id: "proper-motion",
    term: "Proper Motion (mas/yr)",
    shortLabel: "Sky drift",
    definition:
      "The apparent sideways shift of a nearby star or brown dwarf across the background sky over months or years, measured in milliarcseconds per year (mas/yr). Because distant background galaxies stay fixed, nearby fast movers stand out immediately when you blink frames across time.",
    whyItMatters:
      "SPHEREx revisits every patch of sky roughly every 6 months. Subtracting Pass 1 from Pass 2 or Pass 3 turns a moving nearby object into a sharp bright-and-dark dipole pair while stationary stars cancel cleanly out.",
  },
  {
    id: "cold-glow",
    term: "Cold Glow (Band 2 - Band 1 / ~4.4-5.0 um vs ~3.4 um)",
    shortLabel: "Methane infrared excess",
    definition:
      "Very cold objects below ~500 K (like Y-dwarf brown dwarfs or a hypothetical icy Planet 9) barely glow at short near-infrared wavelengths (<3.5 um) where methane absorbs light, but radiate strongly in SPHEREx's longest thermal bands (4.1-5.0 um, Detectors D5 & D6).",
    whyItMatters:
      "Subtracting the scaled short-band sky (D4) from the long thermal band (D5+D6) cancels ordinary hot stars and leaves cool thermal emitters glowing bright amber-orange.",
  },
  {
    id: "survey-pass",
    term: "SPHEREx Survey Pass (~6-month cadence)",
    shortLabel: "Sky visit epoch",
    definition:
      "SPHEREx follows a Sun-synchronous orbit and sweeps great circles orthogonal to the Sun, revisiting most sky locations roughly every 6 months during its primary 2-year all-sky spectrophotometric survey (DR1 + QR3).",
    whyItMatters:
      "Grouping exposures cleanly by temporal pass avoids smearing moving objects and reveals genuine brightness changes and astrometric shifts between visits.",
  },
  {
    id: "sed-spectrum",
    term: "Low-Resolution Spectrum (0.75-5.0 um, 102 channels)",
    shortLabel: "Infrared fingerprint",
    definition:
      "Unlike standard telescopes using a few broad glass filters, SPHEREx uses Linear Variable Filters across six detector arrays (D1-D6), sampling 102 wavelengths continuously from 0.75 um (deep red optical) out to 5.00 um (thermal infrared).",
    whyItMatters:
      "Clicking any pixel in the flipbook extracts the real calibrated flux (MJy/sr) across all six detectors at that sky position—letting you see cool blackbody slopes, water/methane absorption troughs, or disk excess directly.",
  },
  {
    id: "gaia-allwise",
    term: "Gaia DR3 & AllWISE Cross-Match Overlays",
    shortLabel: "Reference anchors",
    definition:
      "Gaia DR3 (optical, epoch 2016.0 with proper motions propagated to the current pass MJD) marks cataloged Milky Way stars, while AllWISE (2010-2011, 3.4 & 4.6 um) shows where infrared sources sat 15 years ago.",
    whyItMatters:
      "An infrared source moving away from its 2010 AllWISE circle—or invisible in optical Gaia entirely—is a classic brown dwarf or solar-system candidate signature.",
  },
  {
    id: "flags-mask",
    term: "SPHEREx Calibration Flags",
    shortLabel: "Artifact protection",
    definition:
      "Per-pixel quality flags attached to each SPHEREx Level 2 exposure marking cosmic rays / transients, detector saturation/overflow, sample-up-the-ramp errors, non-functional pixels, dichroic edge seams, and missing data.",
    whyItMatters:
      "We mask fatal detector errors automatically before computing coadds and spectra, and let you toggle the live FLAGS overlay in Pro Controls so a glitch never masquerades as a discovery.",
  },
];

export const DATA_CAVEAT =
  "Scientific honesty note: Individual SPHEREx Level 2 exposures have ~6.2 arcsec pixels and pass-median sensitivity calibrated to MJy/sr. Tiny faint Solar System bodies below the single-pass background noise floor won't pop out without multi-exposure stacking—this workbench aligns real IRSA DR1+QR3 passes so you can inspect genuine motion, thermal glow, variability, and 102-channel spectra honestly.";
