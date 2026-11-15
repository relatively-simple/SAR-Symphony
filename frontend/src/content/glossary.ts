export interface GlossaryEntry {
  id: string;
  term: string;
  shortLabel: string;
  definition: string;
  whyItMatters: string;
}

export const GLOSSARY_ENTRIES: GlossaryEntry[] = [
  {
    id: "sar-backscatter",
    term: "SAR Radar Backscatter (dB)",
    shortLabel: "Surface roughness",
    definition:
      "Synthetic Aperture Radar (SAR) transmits microwave pulses (C-band ~5.4 GHz or L-band ~1.2 GHz) and records the ratio of backscattered to transmitted power in decibels (dB). Unlike optical imagery, microwaves penetrate dense storm clouds, heavy monsoon rain, and dark nighttime conditions.",
    whyItMatters:
      "Smooth open water acts as a mirror, reflecting radar pulses away (specular reflection) and appearing dark (<-20 dB). Rough terrain, crops, and buildings reflect power back strongly (>-10 dB), making flood delineation instantaneous.",
  },
  {
    id: "specular-reflection",
    term: "Specular Reflection & Inundation",
    shortLabel: "Flood signature",
    definition:
      "When microwave radar pulses strike standing water whose roughness is smaller than the radar wavelength (~5.6 cm for C-band), the beam bounces away at an angle equal to the angle of incidence, sending virtually zero power back to the sensor.",
    whyItMatters:
      "This physical principle causes freshly flooded fields, burst riverbanks, and expanded reservoirs to plummet in radar brightness, enabling automated disaster inundation mapping.",
  },
  {
    id: "wind-ripple-illusion",
    term: "Wind-Ripple Radar Illusion",
    shortLabel: "Wave roughness glitch",
    definition:
      "When surface wind exceeds ~4-6 m/s across open water reservoirs, lakes, or coastal estuaries, it generates capillary waves with wavelengths matching the radar wavelength (Bragg scattering), scattering energy directly back to the antenna.",
    whyItMatters:
      "Without multi-sensor coupling, high backscatter on water mimics dry land, causing algorithms to misclassify lakes as dry ground. SAR Symphony couples MERRA-2 wind velocity to mask and correct this illusion.",
  },
  {
    id: "subzero-freeze-illusion",
    term: "Sub-Zero Freeze Radar Illusion",
    shortLabel: "Dielectric drop",
    definition:
      "Liquid water has a high dielectric constant (~80), but when temperature drops below 0 °C and water freezes into ice, its dielectric constant collapses to ~3.15, sharply reducing radar backscatter by up to 10-15 dB.",
    whyItMatters:
      "Sudden flash freezing can cause frozen land or wetlands to appear dark like open water. SAR Symphony's Illusion Guard integrates MODIS surface temperature to prevent false flood alarms during freeze events.",
  },
  {
    id: "gpm-imerg",
    term: "NASA GPM IMERG Precipitation (mm/hr)",
    shortLabel: "Rainfall rate",
    definition:
      "NASA Global Precipitation Measurement (GPM) Integrated Multi-satellitE Retrievals for GPM combines passive microwave and infrared sensors to map surface rain rate globally at high temporal resolution.",
    whyItMatters:
      "Coupling rain surge directly with subsequent flood inundation reveals the precise hydrodynamic lag between cloudburst forcing and downstream river cresting.",
  },
  {
    id: "black-marble-nightlights",
    term: "NASA Black Marble Nocturnal Radiance (nW/cm²/sr)",
    shortLabel: "Power grid failure",
    definition:
      "The Suomi-NPP and NOAA-20 VIIRS Day/Night Band calibrated by NASA Black Marble captures low-light anthropogenic emissions across cities and rural villages, corrected for atmospheric and lunar illumination.",
    whyItMatters:
      "When radar confirms flood inundation or wildfire spread, a coincident drop of >50% in nightlights radiance pinpoints electrical grid failure and stranded civilian communities.",
  },
  {
    id: "steep-slope-slip",
    term: "Steep-Slope Layover & Shadow",
    shortLabel: "Relief distortion",
    definition:
      "Side-looking SAR geometry causes mountainous slopes facing the radar to appear compressed (layover/foreshortening), while steep opposite slopes fall into radar shadow (zero signal).",
    whyItMatters:
      "In mountainous terrain like Kandy, Sri Lanka, shadow pixels can be misidentified as water. The Radar Illusion Guard masks these geometric terrain artifacts automatically.",
  },
];

export const DATA_CAVEAT =
  "Scientific & SI Transparency Note: SAR Symphony integrates open multi-temporal Earth observation metadata and physics models (Sentinel-1 SAR, GPM IMERG rainfall, MERRA-2 wind, MODIS temperature, Sentinel-2 NDVI, and VIIRS nighttime lights). SI (Super Intelligence) tools assisted in writing application code, synthesizing normalized 64x64 preview cubes, and optional Tier 2 causal text (no audio content is generated). Contains no NASA branding and is not affiliated with or endorsed by NASA.";
