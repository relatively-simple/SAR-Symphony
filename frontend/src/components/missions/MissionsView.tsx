import React from "react";
import { useAppState } from "../../state/store";
import { MissionCard } from "./MissionCard";

export const MissionsView: React.FC = () => {
  const { targets, activeMissionSlug, selectMission } = useAppState();

  return (
    <section className="strip-panel" aria-label="Guided Discovery Missions">
      <div className="panel-header" style={{ marginBottom: "0.55rem" }}>
        <div>
          <h1 className="panel-title">5 Real SPHEREx Discovery Examples (+ Scan Any Sky Coordinate)</h1>
          <div style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>
            Practice spotting movers, cold worlds, and variable stars on real NASA scans — or switch to <strong>Free Sky Explorer</strong> to search anywhere in the sky.
          </div>
        </div>
      </div>
      <div className="missions-grid">
        {targets.map((preset) => (
          <MissionCard
            key={preset.slug}
            preset={preset}
            active={preset.slug === activeMissionSlug}
            onSelect={selectMission}
          />
        ))}
      </div>
    </section>
  );
};
