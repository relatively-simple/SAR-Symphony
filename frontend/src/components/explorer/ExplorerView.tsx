import React from "react";
import { CoordForm } from "./CoordForm";
import { ProgressStages } from "./ProgressStages";

export const ExplorerView: React.FC = () => (
  <section className="strip-panel" aria-label="Free Sky Explorer">
    <div className="panel-header" style={{ marginBottom: "0.55rem" }}>
      <div>
        <h1 className="panel-title">Free Sky Explorer (Any RA / Dec)</h1>
        <div style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>
          Range-read live SPHEREx DR1 &amp; QR3 exposures directly from NASA/IPAC IRSA SIAv2 for any sky coordinate, cropped &amp; ZODI-subtracted on the fly.
        </div>
      </div>
    </div>
    <CoordForm />
    <ProgressStages />
  </section>
);
