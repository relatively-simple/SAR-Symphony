import React from "react";
import { useAppState } from "../../state/store";

export const FlagsToggle: React.FC = () => {
  const { showFlags, setShowFlags, activeFrames, frameIndex } = useAppState();
  const summary = activeFrames[frameIndex]?.flag_summary ?? {};
  const entries = Object.entries(summary).filter(([, count]) => count > 0);

  return (
    <div className="control-row">
      <span style={{ color: "var(--text-muted)", minWidth: "70px" }}>Quality:</span>
      <label style={{ display: "inline-flex", alignItems: "center", gap: "0.4rem", cursor: "pointer" }}>
        <input
          type="checkbox"
          checked={showFlags}
          onChange={(e) => setShowFlags(e.target.checked)}
        />
        <span>Overlay SPHEREx FLAGS mask (magenta = masked error, cyan = transient warning)</span>
      </label>

      {entries.length > 0 && (
        <span className="mono" style={{ fontSize: "0.72rem", color: "var(--text-muted)" }}>
          [{entries.map(([k, v]) => `${k}:${v}`).join(" · ")}]
        </span>
      )}
    </div>
  );
};
