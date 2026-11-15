import React from "react";
import { useAppState } from "../../state/store";

export const OverlayControlsCard: React.FC = () => {
  const {
    overlayGaia,
    setOverlayGaia,
    overlayWise,
    setOverlayWise,
    overlays,
    manifest,
    setAladinOpen,
  } = useAppState();

  return (
    <section className="panel-card" aria-label="Cross-Mission Catalog Overlays">
      <div className="panel-header" style={{ marginBottom: "0.45rem" }}>
        <div>
          <h2 className="panel-title">Cross-Mission Catalog Overlays</h2>
          <div style={{ fontSize: "0.73rem", color: "var(--text-muted)" }}>
            Hidden by default to keep images clutter-free; tick below to reveal reference stars
          </div>
        </div>
        {overlays && (
          <span className="status-pill">
            {overlays.gaia.length} Gaia &middot; {overlays.allwise.length} AllWISE
          </span>
        )}
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem", fontSize: "0.82rem" }}>
        <label style={{ display: "flex", alignItems: "center", gap: "0.5rem", cursor: "pointer" }}>
          <input
            type="checkbox"
            checked={overlayGaia}
            onChange={(e) => setOverlayGaia(e.target.checked)}
          />
          <span style={{ color: "var(--accent-emerald)", fontWeight: 700 }}>+</span>
          <span>
            Gaia DR3 optical stars (PM-propagated dynamically to current pass MJD)
          </span>
        </label>

        <label style={{ display: "flex", alignItems: "center", gap: "0.5rem", cursor: "pointer" }}>
          <input
            type="checkbox"
            checked={overlayWise}
            onChange={(e) => setOverlayWise(e.target.checked)}
          />
          <span style={{ color: "var(--accent-amber)", fontWeight: 700 }}>&#9675;</span>
          <span>
            AllWISE (2010&ndash;2011) 3.4/4.6 &mu;m reference positions (spots 15-yr drift!)
          </span>
        </label>

        {overlays?.note && (
          <div className="callout-box callout-warn" style={{ marginTop: "0.2rem" }}>
            {overlays.note}
          </div>
        )}

        <div style={{ marginTop: "0.25rem", display: "flex", gap: "0.5rem", alignItems: "center" }}>
          <button
            type="button"
            className="btn"
            disabled={!manifest}
            onClick={() => setAladinOpen(true)}
          >
            Inspect Wide Context in Aladin Sky
          </button>
        </div>
      </div>
    </section>
  );
};
