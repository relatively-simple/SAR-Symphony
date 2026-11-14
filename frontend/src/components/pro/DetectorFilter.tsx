import React from "react";
import { useAppState } from "../../state/store";

const DETECTOR_BANDS: Array<{ id: number; band: string }> = [
  { id: 1, band: "D1 (0.75-1.1um)" },
  { id: 2, band: "D2 (1.1-1.6um)" },
  { id: 3, band: "D3 (1.6-2.4um)" },
  { id: 4, band: "D4 (2.4-3.8um)" },
  { id: 5, band: "D5 (3.8-4.4um)" },
  { id: 6, band: "D6 (4.4-5.0um)" },
];

export const DetectorFilter: React.FC = () => {
  const { lens, setLens, detectorFilter, setDetectorFilter, manifest } = useAppState();
  const visitsAvailable = Boolean(manifest?.products.visits);

  if (!visitsAvailable) return null;

  return (
    <div className="control-row">
      <span style={{ color: "var(--text-muted)", minWidth: "70px" }}>Detectors:</span>
      <button
        type="button"
        className={`detector-chip ${lens === "visits" && detectorFilter === null ? "active" : ""}`}
        onClick={() => {
          setLens("visits");
          setDetectorFilter(null);
        }}
      >
        All Raw Visits
      </button>
      {DETECTOR_BANDS.map((d) => (
        <button
          key={d.id}
          type="button"
          className={`detector-chip ${lens === "visits" && detectorFilter === d.id ? "active" : ""}`}
          onClick={() => {
            setLens("visits");
            setDetectorFilter(d.id);
          }}
        >
          {d.band}
        </button>
      ))}
    </div>
  );
};
