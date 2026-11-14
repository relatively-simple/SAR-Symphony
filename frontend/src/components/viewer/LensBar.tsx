import React from "react";
import { LENS_SPECS, PRIMARY_LENSES } from "../../content/lenses";
import { useAppState } from "../../state/store";

export const LensBar: React.FC = () => {
  const { lens, setLens, manifest, proOpen, setProOpen } = useAppState();
  const proVisitAvailable = Boolean(manifest?.products.visits);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "0.45rem" }}>
      <div className="lens-bar">
        {PRIMARY_LENSES.map((id) => {
          const spec = LENS_SPECS[id];
          const available = manifest ? Boolean(manifest.products[spec.productKey]) : true;
          return (
            <button
              key={id}
              type="button"
              className={`lens-pill ${lens === id ? "active" : ""}`}
              onClick={() => setLens(id)}
              disabled={!available}
              title={spec.howToRead}
            >
              {spec.label}
            </button>
          );
        })}

        {proVisitAvailable && (
          <button
            type="button"
            className={`lens-pill ${lens === "visits" ? "active" : ""}`}
            onClick={() => setLens("visits")}
            title={LENS_SPECS.visits.howToRead}
          >
            {LENS_SPECS.visits.shortName}
          </button>
        )}

        <button
          type="button"
          className="btn btn-ghost"
          style={{ marginLeft: "auto", fontSize: "0.76rem", padding: "0.3rem 0.65rem" }}
          onClick={() => setProOpen(!proOpen)}
          aria-expanded={proOpen}
        >
          {proOpen ? "Hide Pro Controls" : "Pro Controls"}
        </button>
      </div>

      <div style={{ fontSize: "0.79rem", color: "var(--text-secondary)" }}>
        <span className="status-pill" style={{ marginRight: "0.5rem" }}>
          {LENS_SPECS[lens].badge}
        </span>
        {LENS_SPECS[lens].howToRead}
      </div>
    </div>
  );
};
