import React from "react";
import type { StretchFn } from "../../api/types";
import { useAppState } from "../../state/store";

export const StretchControls: React.FC = () => {
  const {
    stretchFn,
    setStretchFn,
    loOverride,
    hiOverride,
    setStretchBounds,
    activeFrames,
    frameIndex,
  } = useAppState();

  const hint = activeFrames[frameIndex]?.stretch_hint;
  const currentLo = loOverride ?? hint?.p_lo ?? 0;
  const currentHi = hiOverride ?? hint?.p_hi ?? 1;

  return (
    <div className="control-row">
      <span style={{ color: "var(--text-muted)", minWidth: "70px" }}>Stretch:</span>
      {(["asinh", "linear", "log"] as StretchFn[]).map((fn) => (
        <button
          key={fn}
          type="button"
          className={`detector-chip ${stretchFn === fn ? "active" : ""}`}
          onClick={() => setStretchFn(fn)}
        >
          {fn}
        </button>
      ))}

      <label style={{ display: "inline-flex", alignItems: "center", gap: "0.3rem", marginLeft: "0.4rem" }}>
        <span style={{ color: "var(--text-muted)" }}>Min</span>
        <input
          className="text-input mono"
          style={{ width: "84px", padding: "0.22rem 0.4rem", fontSize: "0.75rem" }}
          type="number"
          step="any"
          value={Number(currentLo.toPrecision(4))}
          onChange={(e) => setStretchBounds(Number(e.target.value), currentHi)}
        />
      </label>

      <label style={{ display: "inline-flex", alignItems: "center", gap: "0.3rem" }}>
        <span style={{ color: "var(--text-muted)" }}>Max</span>
        <input
          className="text-input mono"
          style={{ width: "84px", padding: "0.22rem 0.4rem", fontSize: "0.75rem" }}
          type="number"
          step="any"
          value={Number(currentHi.toPrecision(4))}
          onChange={(e) => setStretchBounds(currentLo, Number(e.target.value))}
        />
      </label>

      <button
        type="button"
        className={`detector-chip ${loOverride !== null || hiOverride !== null ? "active" : ""}`}
        onClick={() => {
          if (loOverride !== null || hiOverride !== null) {
            setStretchBounds(null, null);
          } else {
            setStretchBounds(currentLo, currentHi);
          }
        }}
        title="Freeze Min/Max stretch across frames so true brightness swings stay visible"
      >
        {loOverride !== null || hiOverride !== null ? "Unlock Auto Scale" : "Lock Current Scale"}
      </button>
    </div>
  );
};
