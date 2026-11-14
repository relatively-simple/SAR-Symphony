import React, { useMemo } from "react";
import { useAppState } from "../../state/store";

export const MissionBriefingCard: React.FC = () => {
  const { activePreset, manifest } = useAppState();

  const sparkline = useMemo(() => {
    const coadds = manifest?.frames.pass_coadds;
    if (!coadds || !manifest || manifest.passes.length < 2) return null;

    // Pick a detector present in all (or most) passes so flux compares apples-to-apples
    const nPasses = manifest.passes.length;
    let bestDet: number | null = null;
    let bestCount = -1;
    for (const det of [3, 4, 2, 5, 1, 6]) {
      const pts = coadds.filter((f) => f.detector === det && f.mean_flux_center !== null && f.mean_flux_center !== undefined);
      if (pts.length > bestCount) {
        bestCount = pts.length;
        bestDet = det;
      }
      if (pts.length === nPasses) break;
    }
    if (bestDet === null || bestCount < 2) return null;

    const pts = coadds
      .filter((f) => f.detector === bestDet && typeof f.mean_flux_center === "number")
      .sort((a, b) => a.pass_index - b.pass_index)
      .map((f) => ({
        label: `P${f.pass_index + 1}`,
        val: f.mean_flux_center as number,
        mjd: f.mjd,
      }));
    if (pts.length < 2) return null;
    const minV = Math.min(...pts.map((p) => p.val));
    const maxV = Math.max(...pts.map((p) => p.val));
    const span = Math.max(maxV - minV, Math.abs(maxV) * 0.05, 1e-4);
    return { det: bestDet, pts, minV, maxV, span };
  }, [manifest]);

  return (
    <section className="panel-card" aria-label="Mission Briefing">
      <div className="panel-header" style={{ marginBottom: "0.45rem" }}>
        <h2 className="panel-title">
          {activePreset
            ? `${activePreset.name} — ${activePreset.mission_title}`
            : manifest?.target.name || "Custom Sky Region"}
        </h2>
        {manifest && (
          <span className="status-pill mono">
            {manifest.passes.length} passes &middot; {manifest.source === "preset" ? "Pre-baked" : "Live IRSA"}
          </span>
        )}
      </div>

      {activePreset ? (
        <>
          <p style={{ margin: "0 0 0.5rem", fontSize: "0.84rem", color: "var(--text-secondary)" }}>
            {activePreset.summary}
          </p>

          {activePreset.coord_note && (
            <div className="callout-box" style={{ fontSize: "0.76rem", marginBottom: "0.55rem" }}>
              <strong>Astrometry Note:</strong> {activePreset.coord_note}
            </div>
          )}

          <div style={{ fontSize: "0.78rem", fontWeight: 700, color: "var(--text-muted)", marginTop: "0.4rem" }}>
            HOW TO INSPECT THIS DISCOVERY
          </div>
          <ol className="briefing-steps">
            {activePreset.mission_steps.map((step, i) => (
              <li key={i}>{step}</li>
            ))}
          </ol>

          <div className="callout-box" style={{ marginTop: "0.65rem" }}>
            <strong>What to expect:</strong> {activePreset.what_to_expect}
          </div>

          {sparkline && (
            <div
              style={{
                marginTop: "0.65rem",
                padding: "0.55rem 0.7rem",
                borderRadius: "var(--radius-sm)",
                background: "var(--bg-panel-elevated)",
                border: "1px solid var(--border-subtle)",
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.74rem", marginBottom: "0.3rem" }}>
                <span style={{ fontWeight: 600, color: "var(--text-secondary)" }}>
                  Center Brightness Sparkline (Detector D{sparkline.det})
                </span>
                <span className="mono" style={{ color: "var(--accent-amber)" }}>
                  {sparkline.minV.toFixed(2)} &rarr; {sparkline.maxV.toFixed(2)} MJy/sr
                </span>
              </div>
              <svg viewBox="0 0 220 44" style={{ width: "100%", height: "44px", display: "block" }}>
                <polyline
                  fill="none"
                  stroke="#fbbf24"
                  strokeWidth="2"
                  points={sparkline.pts
                    .map((p, idx) => {
                      const x = 16 + (idx / Math.max(sparkline.pts.length - 1, 1)) * 188;
                      const y = 32 - ((p.val - sparkline.minV) / sparkline.span) * 22;
                      return `${x.toFixed(1)},${y.toFixed(1)}`;
                    })
                    .join(" ")}
                />
                {sparkline.pts.map((p, idx) => {
                  const x = 16 + (idx / Math.max(sparkline.pts.length - 1, 1)) * 188;
                  const y = 32 - ((p.val - sparkline.minV) / sparkline.span) * 22;
                  return (
                    <g key={p.label}>
                      <circle cx={x} cy={y} r="3.2" fill="#38bdf8" />
                      <text x={x} y="42" textAnchor="middle" fontSize="8" fill="#94a3b8">
                        {p.label}
                      </text>
                    </g>
                  );
                })}
              </svg>
            </div>
          )}

          {activePreset.caveat && (
            <div className="callout-box callout-warn">
              <strong>Science caveat:</strong> {activePreset.caveat}
            </div>
          )}
        </>
      ) : (
        <p style={{ margin: 0, fontSize: "0.84rem", color: "var(--text-secondary)" }}>
          {manifest
            ? `Custom sky stack centered at RA ${manifest.grid.ra0.toFixed(5)}°, Dec ${manifest.grid.dec0.toFixed(5)}° (${manifest.passes.length} SPHEREx passes). Switch lenses on the left or click any pixel to extract its 0.75-5.0 um infrared spectrum.`
            : "Choose a Discovery Mission above or switch to Free Sky Explorer to query any sky coordinate."}
        </p>
      )}

      {manifest &&
        (() => {
          const extraWarnings = manifest.warnings.filter(
            (w) => !activePreset?.caveat || w.trim() !== activePreset.caveat.trim()
          );
          if (extraWarnings.length === 0) return null;
          return (
            <div className="callout-box callout-warn" style={{ marginTop: "0.6rem" }}>
              {extraWarnings.map((w, i) => (
                <div key={i}>{w}</div>
              ))}
            </div>
          );
        })()}
    </section>
  );
};
