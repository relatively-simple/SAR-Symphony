import React from "react";
import type { TargetPreset } from "../../api/types";

const KIND_BADGE: Record<TargetPreset["kind"], string> = {
  mover: "Fast Mover",
  binary_bd: "Cold Brown Dwarf",
  variable: "Variable Star",
};

interface MissionCardProps {
  preset: TargetPreset;
  active: boolean;
  onSelect: (slug: string) => void;
}

export const MissionCard: React.FC<MissionCardProps> = ({ preset, active, onSelect }) => {
  return (
    <button
      type="button"
      className={`mission-card ${active ? "active" : ""}`}
      onClick={() => onSelect(preset.slug)}
      aria-pressed={active}
    >
      <div className="mission-top">
        <img
          className="mission-thumb"
          src={`/api/targets/${encodeURIComponent(preset.slug)}/thumb.webp`}
          alt={`${preset.name} preview`}
          loading="lazy"
          onError={(e) => {
            (e.currentTarget as HTMLImageElement).style.opacity = "0.25";
          }}
        />
        <div>
          <span className="mission-tag">{KIND_BADGE[preset.kind]}</span>
          <div className="mission-name">{preset.name}</div>
          <div className="mission-sub">{preset.mission_title}</div>
        </div>
      </div>
      <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)", lineHeight: 1.35 }}>
        {preset.summary.slice(0, 108)}
        {preset.summary.length > 108 ? "..." : ""}
      </div>
    </button>
  );
};
