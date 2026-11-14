import React from "react";
import { useAppState } from "../../state/store";

export const CitationsBar: React.FC = () => {
  const { manifest } = useAppState();
  const citations = manifest?.citations ?? [];

  return (
    <footer className="citations-footer">
      <div style={{ display: "flex", flexWrap: "wrap", gap: "0.75rem", justifyContent: "space-between" }}>
        <span>
          <strong>Team KurinjiKumaraN</strong> &middot; Apache-2.0 Open Source &middot; NASA/IPAC IRSA SPHEREx Level 2 Images (DR1 DOI: 10.26131/IRSA678 &middot; QR3 DOI: 10.26131/IRSA662)
        </span>
        <span className="mono">Epoch-aligned ICRS North-Up &middot; Zero-API Public Archive</span>
      </div>
      {citations.length > 0 && (
        <div style={{ display: "flex", flexWrap: "wrap", gap: "0.9rem" }}>
          {citations.map((c, idx) => (
            <span key={idx}>
              <strong>{c.label}:</strong> {c.text}{" "}
              {c.doi && (
                <a href={`https://doi.org/${c.doi}`} target="_blank" rel="noreferrer">
                  doi:{c.doi}
                </a>
              )}
            </span>
          ))}
        </div>
      )}
    </footer>
  );
};
