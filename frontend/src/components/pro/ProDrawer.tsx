import React from "react";
import { useAppState } from "../../state/store";
import { DetectorFilter } from "./DetectorFilter";
import { FlagsToggle } from "./FlagsToggle";
import { StretchControls } from "./StretchControls";

export const ProDrawer: React.FC = () => {
  const { proOpen } = useAppState();
  if (!proOpen) return null;

  return (
    <div className="pro-drawer" role="region" aria-label="Pro Inspector Controls">
      <div style={{ fontSize: "0.75rem", fontWeight: 700, color: "var(--accent-cyan)", textTransform: "uppercase" }}>
        Pro Controls &mdash; Stretch, Spectral Detectors &amp; Bitmask Inspection
      </div>
      <StretchControls />
      <DetectorFilter />
      <FlagsToggle />
    </div>
  );
};
