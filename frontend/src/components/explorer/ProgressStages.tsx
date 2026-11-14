import React from "react";
import { useAppState } from "../../state/store";

const STAGE_ORDER = ["resolve", "query", "plan", "fetch", "process"] as const;
const STAGE_LABELS: Record<(typeof STAGE_ORDER)[number], string> = {
  resolve: "1. Resolve Sky",
  query: "2. Query IRSA",
  plan: "3. Group Passes",
  fetch: "4. Range-Read",
  process: "5. Align & Stack",
};

export const ProgressStages: React.FC = () => {
  const { exploring, exploreProgress, exploreError } = useAppState();
  if (!exploring && !exploreProgress && !exploreError) return null;

  const currentIdx = exploreProgress
    ? exploreProgress.stage === "done"
      ? STAGE_ORDER.length
      : STAGE_ORDER.indexOf(exploreProgress.stage as (typeof STAGE_ORDER)[number])
    : -1;

  return (
    <div style={{ marginTop: "0.65rem" }}>
      {exploreError ? (
        <div className="callout-box callout-warn" role="alert">
          <strong>Explorer notice:</strong> {exploreError}
        </div>
      ) : (
        <>
          <div style={{ fontSize: "0.8rem", color: "var(--text-secondary)" }}>
            {exploreProgress?.message}
          </div>
          <div className="progress-stages">
            {STAGE_ORDER.map((s, idx) => {
              const cls = idx < currentIdx ? "done" : idx === currentIdx ? "active" : "";
              return (
                <div key={s} className={`stage-pill ${cls}`}>
                  {STAGE_LABELS[s]}
                </div>
              );
            })}
          </div>
        </>
      )}
    </div>
  );
};
