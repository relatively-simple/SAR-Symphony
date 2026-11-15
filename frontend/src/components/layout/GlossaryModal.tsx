import React from "react";
import { DATA_CAVEAT, GLOSSARY_ENTRIES } from "../../content/glossary";
import { useAppState } from "../../state/store";

export const GlossaryModal: React.FC = () => {
  const { glossaryOpen, setGlossaryOpen } = useAppState();
  if (!glossaryOpen) return null;

  return (
    <div
      className="modal-backdrop"
      role="dialog"
      aria-modal="true"
      aria-label="SAR Science Guide"
      onClick={() => setGlossaryOpen(false)}
    >
      <div className="modal-card" onClick={(e) => e.stopPropagation()} style={{ maxWidth: "800px" }}>
        <div className="panel-header">
          <h2 className="panel-title">
            SAR Symphony &mdash; Synthetic Aperture Radar &amp; Earth Observation Guide
          </h2>
          <button type="button" className="btn btn-ghost" onClick={() => setGlossaryOpen(false)}>
            ✕ Close
          </button>
        </div>

        <div className="callout-box callout-warn" style={{ marginBottom: "1rem" }}>
          {DATA_CAVEAT}
        </div>

        <div style={{ display: "grid", gap: "0.85rem", maxHeight: "65vh", overflowY: "auto" }}>
          {GLOSSARY_ENTRIES.map((g) => (
            <div
              key={g.id}
              style={{
                padding: "0.75rem",
                background: "var(--bg-panel-elevated)",
                borderRadius: "var(--radius-md)",
                border: "1px solid var(--border-subtle)",
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <strong>{g.term}</strong>
                <span className="status-pill">{g.shortLabel}</span>
              </div>
              <p style={{ margin: "0.4rem 0", fontSize: "0.84rem", color: "var(--text-secondary)" }}>
                {g.definition}
              </p>
              <p style={{ margin: 0, fontSize: "0.8rem", color: "var(--accent-cyan)" }}>
                Physical Relevance: {g.whyItMatters}
              </p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
