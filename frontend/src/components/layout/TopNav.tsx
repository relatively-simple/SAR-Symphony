import React from "react";
import { useAppState } from "../../state/store";

export const TopNav: React.FC = () => {
  const {
    mode,
    setMode,
    setGlossaryOpen,
    trainingPhase,
    replayTraining,
    discoveryPoints,
    hunterRank,
    health,
  } = useAppState();

  const isSolo = trainingPhase === "solo";

  return (
    <header className="topbar">
      <div className="brand">
        <div className="brand-mark">KK</div>
        <div>
          <div className="brand-title">SPHEREx Discovery Flipbook</div>
          <div className="brand-sub">Team KurinjiKumaraN &middot; Citizen Planet X Workbench</div>
        </div>
      </div>

      <nav className="nav-tabs" aria-label="Workspace mode">
        <button
          type="button"
          className={`nav-tab ${mode === "missions" ? "active" : ""}`}
          onClick={() => setMode("missions")}
        >
          {isSolo ? "Discovery Examples" : "Training Missions"}
        </button>
        <button
          type="button"
          className={`nav-tab ${mode === "explorer" ? "active" : ""}`}
          disabled={!isSolo}
          title={
            isSolo
              ? "Scan any sky coordinate directly from NASA IRSA archives"
              : "Complete 2-round training (or click Skip Training) to unlock Free Sky Explorer"
          }
          onClick={() => setMode("explorer")}
        >
          Free Sky Explorer {!isSolo ? " (Solo)" : ""}
        </button>
      </nav>

      <div className="nav-actions">
        {!isSolo && (
          <span className="status-pill" style={{ borderColor: "rgba(251, 191, 36, 0.45)", color: "var(--accent-amber)" }}>
            {trainingPhase === "round1-demo"
              ? "Round 1/2 · Demo"
              : trainingPhase === "round2-test1"
              ? "Round 2/2 · Check 1"
              : "Round 2/2 · Check 2"}
          </span>
        )}
        <span
          className="status-pill score-pill"
          title="Earn points from training and independent sky discoveries"
        >
          &#9733; {discoveryPoints} pts &middot; {hunterRank}
        </span>
        {health && (
          <span
            className="status-pill"
            title="Live connection status to NASA/IPAC IRSA SIAv2 archive"
          >
            {health.irsa_ok ? "IRSA Live" : "Offline"}
          </span>
        )}
        {isSolo && (
          <button type="button" className="btn btn-ghost" onClick={replayTraining}>
            Replay Training
          </button>
        )}
        <button
          type="button"
          className="btn btn-ghost"
          onClick={() => setGlossaryOpen(true)}
        >
          FAQ
        </button>
      </div>
    </header>
  );
};
