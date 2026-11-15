import React from "react";
import { useAppState } from "../../state/store";
import { DetectorFilter } from "./DetectorFilter";
import { FlagsToggle } from "./FlagsToggle";
import { StretchControls } from "./StretchControls";

export const ProDrawer: React.FC = () => {
  const { proOpen, cleanMode, setCleanMode, crispPixels, setCrispPixels } = useAppState();
  if (!proOpen) return null;

  return (
    <div className="pro-drawer" role="region" aria-label="Pro Inspector Controls">
      <div style={{ fontSize: "0.75rem", fontWeight: 700, color: "var(--accent-cyan)", textTransform: "uppercase" }}>
        Pro Controls &mdash; Clean Gate, Pixel Mode, Stretch &amp; Flags
      </div>
      <div style={{ display: "flex", flexWrap: "wrap", gap: "1rem", fontSize: "0.78rem", margin: "0.45rem 0 0.2rem" }}>
        <label style={{ display: "flex", alignItems: "center", gap: "0.35rem", cursor: "pointer" }}>
          <input
            type="checkbox"
            checked={cleanMode}
            onChange={(e) => setCleanMode(e.target.checked)}
          />
          <span>Clean Sky Noise Gate (suppress faint &lt;2.3&sigma; background mud)</span>
        </label>
        <label style={{ display: "flex", alignItems: "center", gap: "0.35rem", cursor: "pointer" }}>
          <input
            type="checkbox"
            checked={crispPixels}
            onChange={(e) => setCrispPixels(e.target.checked)}
          />
          <span>Crisp Detector Pixels (disable bilinear blur)</span>
        </label>
      </div>
      <StretchControls />
      <DetectorFilter />
      <FlagsToggle />
    </div>
  );
};
