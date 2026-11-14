import React, { useEffect, useRef } from "react";
import Plotly from "plotly.js-basic-dist-min";
import { useAppState } from "../../state/store";
import { Spinner } from "../common/Spinner";

const DETECTOR_COLORS: Record<number, { color: string; name: string }> = {
  1: { color: "#60a5fa", name: "D1 (0.75-1.1 um)" },
  2: { color: "#34d399", name: "D2 (1.1-1.65 um)" },
  3: { color: "#a3e635", name: "D3 (1.65-2.4 um)" },
  4: { color: "#facc15", name: "D4 (2.4-3.8 um)" },
  5: { color: "#fb923c", name: "D5 (3.8-4.4 um)" },
  6: { color: "#f87171", name: "D6 (4.4-5.0 um)" },
};

export const SpectrumChart: React.FC = () => {
  const {
    manifest,
    selectedCoord,
    pickCoordinate,
    spectrum,
    spectrumLoading,
    spectrumError,
  } = useAppState();
  const plotRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const el = plotRef.current;
    if (!el || !spectrum || spectrum.points.length === 0) return;

    const traces: any[] = [];
    for (let det = 1; det <= 6; det++) {
      const pts = spectrum.points.filter((p) => p.detector === det);
      if (pts.length === 0) continue;
      const spec = DETECTOR_COLORS[det];
      traces.push({
        type: "scatter",
        mode: "markers",
        name: spec.name,
        x: pts.map((p) => p.wavelength_um),
        y: pts.map((p) => p.flux_mjysr),
        error_y: {
          type: "data",
          array: pts.map((p) => p.err),
          visible: true,
          thickness: 1.1,
          width: 2,
          color: spec.color,
        },
        marker: {
          color: spec.color,
          size: 7,
          symbol: pts.map((p) => (p.flagged ? "diamond-open" : "circle")),
          line: { width: 1.2, color: "#0f1626" },
        },
        text: pts.map(
          (p) =>
            `${p.wavelength_um.toFixed(3)} um<br>${p.flux_mjysr.toFixed(2)} ± ${p.err.toFixed(2)} MJy/sr<br>D${p.detector} · MJD ${p.mjd.toFixed(1)}${p.flagged ? " (flagged)" : ""}`
        ),
        hoverinfo: "text",
      });
    }

    Plotly.react(
      el,
      traces,
      {
        paper_bgcolor: "rgba(0,0,0,0)",
        plot_bgcolor: "#090f1d",
        font: { color: "#cbd5e1", size: 11, family: "Inter, sans-serif" },
        margin: { l: 52, r: 12, t: 12, b: 40 },
        height: 255,
        xaxis: {
          title: "Wavelength (um) · SPHEREx D1-D6",
          range: [0.65, 5.1],
          gridcolor: "rgba(148,163,184,0.14)",
          zeroline: false,
        },
        yaxis: {
          title: "Flux (MJy/sr)",
          gridcolor: "rgba(148,163,184,0.14)",
          zerolinecolor: "rgba(148,163,184,0.3)",
        },
        legend: {
          orientation: "h",
          y: 1.18,
          x: 0,
          font: { size: 10 },
        },
      },
      { displayModeBar: false, responsive: true }
    );

    return () => {
      if (el) Plotly.purge(el);
    };
  }, [spectrum]);

  return (
    <section className="panel-card" aria-label="Click-to-Spectrum Plot">
      <div className="panel-header" style={{ marginBottom: "0.4rem" }}>
        <div>
          <h2 className="panel-title">0.75&ndash;5.0 &mu;m Click-to-Spectrum</h2>
          {selectedCoord && (
            <div className="mono" style={{ fontSize: "0.74rem", color: "var(--text-muted)" }}>
              RA {selectedCoord.ra.toFixed(5)}&deg;, Dec {selectedCoord.dec.toFixed(5)}&deg;
            </div>
          )}
        </div>
        {manifest && (
          <div style={{ display: "flex", gap: "0.4rem" }}>
            {spectrum && spectrum.points.length > 0 && (
              <button
                type="button"
                className="btn btn-ghost"
                style={{ fontSize: "0.74rem", padding: "0.28rem 0.6rem" }}
                onClick={() => {
                  const rows = [
                    "wavelength_um,flux_mjysr,err,detector,mjd,obs_id,flagged",
                    ...spectrum.points.map(
                      (p) =>
                        `${p.wavelength_um},${p.flux_mjysr},${p.err},${p.detector},${p.mjd},${p.obs_id},${p.flagged}`
                    ),
                  ];
                  const blob = new Blob([rows.join("\n")], { type: "text/csv;charset=utf-8" });
                  const url = URL.createObjectURL(blob);
                  const a = document.createElement("a");
                  a.href = url;
                  a.download = `spherex_spectrum_${spectrum.ra.toFixed(4)}_${spectrum.dec.toFixed(4)}.csv`;
                  a.click();
                  URL.revokeObjectURL(url);
                }}
              >
                Export CSV
              </button>
            )}
            <button
              type="button"
              className="btn btn-ghost"
              style={{ fontSize: "0.74rem", padding: "0.28rem 0.6rem" }}
              onClick={() => pickCoordinate(manifest.target.ra, manifest.target.dec)}
            >
              Center Target
            </button>
          </div>
        )}
      </div>

      {spectrumLoading ? (
        <div style={{ padding: "2.2rem 0", textAlign: "center" }}>
          <Spinner label="Evaluating SPHEREx WCS-WAVE detectors..." />
        </div>
      ) : spectrumError ? (
        <div className="callout-box callout-warn">{spectrumError}</div>
      ) : spectrum && spectrum.points.length > 0 ? (
        <>
          <div ref={plotRef} style={{ width: "100%", minHeight: "255px" }} />
          <div style={{ fontSize: "0.74rem", color: "var(--text-muted)", marginTop: "0.3rem" }}>
            {spectrum.n_used} calibrated points across SPHEREx LVF detectors ({spectrum.n_rejected} masked/edge visits excluded).
            {spectrum.note ? ` ${spectrum.note}` : ""}
          </div>
        </>
      ) : (
        <div className="callout-box callout-warn">
          {spectrum?.note || "Click any star or patch on the sky image to extract its SPHEREx spectrum."}
        </div>
      )}
    </section>
  );
};
