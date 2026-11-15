import React from "react";
import { useAppState } from "../../state/store";

export const TopNav: React.FC = () => {
  const {
    mode,
    setMode,
    setGlossaryOpen,
    setTutorialOpen,
    discoveryPoints,
    hunterRank,
    health,
  } = useAppState();

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
          Sample Sky Patches
        </button>
        <button
          type="button"
          className={`nav-tab ${mode === "explorer" ? "active" : ""}`}
          onClick={() => setMode("explorer")}
        >
          Free Sky Explorer
        </button>
      </nav>

      <div className="nav-actions">
        <span
          className="status-pill score-pill"
          title="Earn points by completing the tutorial practice & verifying auto-detected sky patterns"
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
        <button
          type="button"
          className="btn btn-ghost"
          onClick={() => setTutorialOpen(true)}
        >
          Tutorial
        </button>
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
