import React from "react";
import { useAppState } from "../../state/store";

const TOUR_STEPS = [
  {
    step: 0,
    title: "1. Trace Upwind Causes Visually",
    desc: "Start with any flood, cyclone, wildfire, or drought. Watch how upstream warmth and wind patterns drive downstream impacts across scales.",
    badge: "Cause → Effect",
  },
  {
    step: 1,
    title: "2. 6 Equal NASA Datasets Synchronized",
    desc: "MODIS Temperature, MERRA-2 Wind, GPM Rain, Optical NDVI, Sentinel-1/NISAR SAR Radar, and Black Marble Nightlights appear side-by-side.",
    badge: "6 NASA Feeds",
  },
  {
    step: 2,
    title: "3. 5-Step Domino Story & Camera Flight",
    desc: "Click Play Story or any card 1–5 to fly the interactive map from upwind origin down into surface impact.",
    badge: "Domino Sequence",
  },
  {
    step: 3,
    title: "4. AI Lead-Lag & Radar Illusion Guard",
    desc: "The Cause → Effect diagram measures lag hours between datasets and flags wind-wave or flash-freeze SAR radar illusions.",
    badge: "AI Guard",
  },
  {
    step: 4,
    title: "5. Search Disasters or Probe the Map",
    desc: "Search 'Kandy flood', 'Dubai flood 2024', pick live NASA EONET hazards, or click anywhere on the map to sample all 6 NASA curves.",
    badge: "Interactive Probe",
  },
];

export const TrainingDirectorBar: React.FC = () => {
  const {
    guidedTourActive,
    guidedTourStep,
    nextTourStep,
    prevTourStep,
    stopGuidedTour,
  } = useAppState();

  if (!guidedTourActive) return null;

  const current = TOUR_STEPS[guidedTourStep] || TOUR_STEPS[0];
  const isFirst = guidedTourStep === 0;
  const isLast = guidedTourStep === TOUR_STEPS.length - 1;

  return (
    <div className="tour-floating-banner" role="dialog" aria-label="60-Second Guided Tour">
      <div className="tour-top-row">
        <span className="phase-chip">
          {current.badge} · Step {guidedTourStep + 1} of 5
        </span>
        <button type="button" className="btn btn-ghost btn-xs" onClick={stopGuidedTour}>
          ✕ Close
        </button>
      </div>
      <div className="tour-heading">{current.title}</div>
      <p className="tour-body">{current.desc}</p>
      <div className="tour-actions">
        {!isFirst && (
          <button type="button" className="btn btn-ghost btn-xs" onClick={prevTourStep}>
            Prev
          </button>
        )}
        {!isLast ? (
          <button type="button" className="btn btn-coral btn-xs" onClick={nextTourStep}>
            Next
          </button>
        ) : (
          <button type="button" className="btn btn-teal btn-xs" onClick={stopGuidedTour}>
            Finish
          </button>
        )}
      </div>
    </div>
  );
};
