import React from "react";

export const Spinner: React.FC<{ label?: string }> = ({ label }) => (
  <span style={{ display: "inline-flex", alignItems: "center", gap: "0.45rem" }}>
    <span className="spinner" aria-hidden="true" />
    {label && <span style={{ fontSize: "0.82rem", color: "var(--text-secondary)" }}>{label}</span>}
  </span>
);
