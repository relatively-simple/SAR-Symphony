import React, { useEffect, useMemo, useRef } from "react";
import Plotly from "plotly.js-basic-dist-min";
import type { SignalId } from "../../api/types";
import { useAppState } from "../../state/store";
import { Spinner } from "../common/Spinner";

interface SignalConfig {
  id: SignalId;
  name: string;
  unit: string;
  color: string;
}

const SIGNALS: SignalConfig[] = [
  { id: "temp", name: "Temp", unit: "°C", color: "#f97316" },
  { id: "wind", name: "Wind", unit: "m/s", color: "#14b8a6" },
  { id: "rain", name: "Rain", unit: "mm/d", color: "#3b82f6" },
  { id: "optical", name: "NDVI", unit: "", color: "#10b981" },
  { id: "radar", name: "SAR", unit: "dB", color: "#a855f7" },
  { id: "nightlights", name: "Lights", unit: "nW", color: "#eab308" },
];

function formatShortDate(iso: string): string {
  const clean = iso.split("T")[0] || iso;
  const d = new Date(`${clean}T00:00:00Z`);
  if (Number.isNaN(d.getTime())) return clean.slice(5);
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric", timeZone: "UTC" });
}

export const SpectrumChart: React.FC = () => {
  const {
    manifest,
    selectedCoord,
    pickCoordinate,
    spectrum,
    spectrumLoading,
    spectrumError,
    frameIndex,
    setFrameIndex,
    activeLayers,
  } = useAppState();

  const plotRef = useRef<HTMLDivElement | null>(null);

  const rawDates = useMemo(() => {
    if (manifest?.event_dates && manifest.event_dates.length > 0) {
      return manifest.event_dates;
    }
    if (spectrum?.dates && spectrum.dates.length > 0) {
      return spectrum.dates.map((d) => d.split("T")[0] || d);
    }
    return Array.from({ length: 12 }, (_, i) => `Day ${i + 1}`);
  }, [manifest?.event_dates, spectrum?.dates]);

  const shortDates = useMemo(() => rawDates.map(formatShortDate), [rawDates]);

  const rawSeries = useMemo(() => {
    const out: Record<SignalId, number[]> = {
      temp: Array(12).fill(25),
      wind: Array(12).fill(8),
      rain: Array(12).fill(5),
      optical: Array(12).fill(0.55),
      radar: Array(12).fill(-12),
      nightlights: Array(12).fill(35),
    };
    if (spectrum?.series) {
      for (const sig of SIGNALS) {
        const arr = spectrum.series[sig.id];
        if (Array.isArray(arr) && arr.length > 0) {
          out[sig.id] = arr.map((v) => Number(v));
        }
      }
    }
    return out;
  }, [spectrum]);

  useEffect(() => {
    const el = plotRef.current;
    if (!el) return;

    // Normalize each of the 6 physical signals onto a shared 0..100% excursion index
    // so mm/day precipitation never flattens NDVI (0..1) or SAR backscatter (-25..-5 dB).
    const traces: any[] = SIGNALS.map((sig) => {
      const vals = rawSeries[sig.id] || [];
      let minV = Math.min(...vals);
      let maxV = Math.max(...vals);
      if (!Number.isFinite(minV) || !Number.isFinite(maxV) || maxV - minV < 1e-4) {
        minV = 0;
        maxV = 1;
      }
      const normVals = vals.map((v) => ((v - minV) / (maxV - minV)) * 100);
      const isActive = activeLayers.includes(sig.id);

      return {
        type: "scatter",
        mode: "lines+markers",
        name: sig.name,
        x: shortDates,
        y: normVals,
        line: {
          color: sig.color,
          width: isActive ? 3.2 : 1.5,
          dash: isActive ? "solid" : "dot",
        },
        marker: {
          color: sig.color,
          size: isActive ? 6 : 4,
        },
        opacity: isActive ? 1.0 : 0.45,
        hoverinfo: "text",
        text: vals.map((v, i) => {
          const valStr = sig.id === "optical" ? v.toFixed(2) : v.toFixed(1);
          return `${rawDates[i]}<br>${sig.name}: <b>${valStr} ${sig.unit}</b>`;
        }),
      };
    });

    const cursorLabel = shortDates[Math.min(frameIndex, shortDates.length - 1)] || shortDates[0];

    const layout: any = {
      paper_bgcolor: "rgba(0,0,0,0)",
      plot_bgcolor: "#090f1d",
      font: { color: "#cbd5e1", size: 10, family: "Inter, sans-serif" },
      margin: { l: 34, r: 8, t: 26, b: 26 },
      height: 195,
      shapes: [
        {
          type: "line",
          xref: "x",
          yref: "paper",
          x0: cursorLabel,
          x1: cursorLabel,
          y0: 0,
          y1: 1,
          line: { color: "#f97316", width: 2 },
        },
      ],
      xaxis: {
        type: "category",
        nticks: 6,
        gridcolor: "rgba(148,163,184,0.12)",
        tickfont: { size: 9 },
        tickangle: 0,
      },
      yaxis: {
        title: "Signal %",
        range: [-6, 108],
        gridcolor: "rgba(148,163,184,0.12)",
        tickfont: { size: 9 },
      },
      legend: {
        orientation: "h",
        y: 1.22,
        x: 0,
        font: { size: 9 },
      },
      annotations: [
        {
          text: "SI-gen",
          xref: "paper",
          yref: "paper",
          x: 0.995,
          y: 0.02,
          xanchor: "right",
          yanchor: "bottom",
          showarrow: false,
          font: { size: 7, color: "rgba(148,163,184,0.30)" },
        },
      ],
      hovermode: "closest",
    };

    Plotly.react(el, traces, layout, { displayModeBar: false, responsive: true });

    const handleClick = (data: any) => {
      const ptIdx = data?.points?.[0]?.pointIndex;
      if (typeof ptIdx === "number") {
        setFrameIndex(ptIdx);
      }
    };
    (el as any).on?.("plotly_click", handleClick);
    return () => {
      (el as any).removeAllListeners?.("plotly_click");
    };
  }, [rawDates, shortDates, rawSeries, activeLayers, frameIndex, setFrameIndex]);

  const handleExportCsv = () => {
    const headers = ["Date", "Temp_C", "Wind_ms", "Rain_mmd", "Optical_NDVI", "Radar_dB", "Nightlights_nW"];
    const rows = rawDates.map((d, i) => [
      d,
      (rawSeries.temp[i] ?? 0).toFixed(2),
      (rawSeries.wind[i] ?? 0).toFixed(2),
      (rawSeries.rain[i] ?? 0).toFixed(2),
      (rawSeries.optical[i] ?? 0).toFixed(3),
      (rawSeries.radar[i] ?? 0).toFixed(2),
      (rawSeries.nightlights[i] ?? 0).toFixed(2),
    ]);
    const disclosureHeader = [
      "# SAR Symphony (Team KurinjiKumaraN) — SI-assisted multi-sensor data export",
      "# Uses open Earth observation data; no NASA branding or endorsement implied.",
    ];
    const csv = [...disclosureHeader, headers.join(","), ...rows.map((r) => r.join(","))].join("\n");
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    const slug = (manifest?.target.name || "event").toLowerCase().replace(/[^a-z0-9]+/g, "_");
    a.download = `sar_symphony_${slug}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <section className="panel-card chart-card" aria-label="6-Signal Earth Rhythm">
      <div className="panel-header-compact">
        <div className="panel-head-text">
          <h2 className="panel-title-sm">📊 6-Signal Timeline</h2>
          <div className="mono panel-sub-sm">
            {selectedCoord
              ? `${selectedCoord.dec >= 0 ? `${selectedCoord.dec.toFixed(2)}°N` : `${Math.abs(selectedCoord.dec).toFixed(2)}°S`}, ${
                  selectedCoord.ra >= 0 ? `${selectedCoord.ra.toFixed(2)}°E` : `${Math.abs(selectedCoord.ra).toFixed(2)}°W`
                }`
              : "Normalized 0–100% excursion"}
          </div>
        </div>
        <div className="chart-head-actions">
          <button type="button" className="btn btn-ghost btn-xs" onClick={handleExportCsv}>
            Export CSV
          </button>
          {manifest && (
            <button
              type="button"
              className="btn btn-teal btn-xs"
              onClick={() => pickCoordinate(manifest.target.lon ?? manifest.target.ra, manifest.target.lat ?? manifest.target.dec)}
            >
              Center
            </button>
          )}
        </div>
      </div>

      {spectrumLoading ? (
        <div style={{ padding: "1.6rem 0", textAlign: "center" }}>
          <Spinner label="Syncing 6 NASA datasets..." />
        </div>
      ) : spectrumError ? (
        <div className="callout-box callout-warn">{spectrumError}</div>
      ) : (
        <div ref={plotRef} className="plotly-host" />
      )}
    </section>
  );
};
