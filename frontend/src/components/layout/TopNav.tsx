import React from "react";
import { useAppState } from "../../state/store";

export const TopNav: React.FC = () => {
  const { mode, setMode, setGlossaryOpen, health } = useAppState();

  return (
    <header className="topbar">
      <div className="brand">
        <div className="brand-mark">KK</div>
        <div>
          <div className="brand-title">SPHEREx Discovery Flipbook</div>
          <div className="brand-sub">Team KurinjiKumaraN &middot; Challenge 12 Workbench</div>
        </div>
      </div>

      <nav className="nav-tabs" aria-label="Workspace mode">
        <button
          type="button"
          className={`nav-tab ${mode === "missions" ? "active" : ""}`}
          onClick={() => setMode("missions")}
        >
          Guided Discovery Missions
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
        {health && (
          <span
            className="status-pill"
            title="Live connection status to NASA/IPAC IRSA SIAv2 archive"
          >
            {health.presets_ready.length}/5 presets &middot;{" "}
            {health.irsa_ok ? "IRSA Online" : "Offline Presets"}
          </span>
        )}
        <button
          type="button"
          className="btn btn-ghost"
          onClick={() => setGlossaryOpen(true)}
        >
          Science Guide &amp; FAQ
        </button>
      </div>
    </header>
  );
};
