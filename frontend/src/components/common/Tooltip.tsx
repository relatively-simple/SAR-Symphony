import React from "react";

export const TooltipHint: React.FC<{ title: string; label?: string }> = ({ title, label = "?" }) => (
  <span
    title={title}
    style={{
      display: "inline-flex",
      alignItems: "center",
      justifyContent: "center",
      width: "16px",
      height: "16px",
      borderRadius: "50%",
      border: "1px solid var(--border-strong)",
      fontSize: "0.68rem",
      color: "var(--text-muted)",
      cursor: "help",
      marginLeft: "0.3rem",
    }}
  >
    {label}
  </span>
);
