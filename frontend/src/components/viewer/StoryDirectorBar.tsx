import React from "react";
import type { SignalId, StoryScene } from "../../api/types";
import { useAppState } from "../../state/store";

const STEP_COLORS = ["#f97316", "#14b8a6", "#3b82f6", "#a855f7", "#f43f5e"];

interface SignalPillSpec {
  id: SignalId;
  shortLabel: string;
  agency: string;
  unit: string;
  color: string;
  icon: string;
}

const SIX_NASA_DATASETS: SignalPillSpec[] = [
  { id: "temp", shortLabel: "Temp", agency: "MODIS", unit: "°C", color: "#f97316", icon: "🌡️" },
  { id: "wind", shortLabel: "Wind", agency: "MERRA-2", unit: "m/s", color: "#14b8a6", icon: "💨" },
  { id: "rain", shortLabel: "Rain", agency: "GPM", unit: "mm/d", color: "#3b82f6", icon: "🌧️" },
  { id: "optical", shortLabel: "NDVI", agency: "VIIRS", unit: "", color: "#10b981", icon: "🌱" },
  { id: "radar", shortLabel: "SAR Radar", agency: "Sentinel-1", unit: "dB", color: "#a855f7", icon: "📡" },
  { id: "nightlights", shortLabel: "Night Lights", agency: "Black Marble", unit: "nW", color: "#eab308", icon: "💡" },
];

function formatCompactDate(raw?: string | null): string {
  if (!raw) return "";
  const isoMatch = raw.match(/\d{4}-\d{2}-\d{2}/);
  if (isoMatch) {
    const d = new Date(`${isoMatch[0]}T00:00:00Z`);
    if (!Number.isNaN(d.getTime())) {
      return d.toLocaleDateString("en-US", { month: "short", day: "numeric", timeZone: "UTC" });
    }
  }
  // Handle "Nov 18, 2024" -> "Nov 18"
  const commaIdx = raw.indexOf(",");
  if (commaIdx > 0) return raw.slice(0, commaIdx).trim();
  return raw.trim();
}

export const StoryDirectorBar: React.FC = () => {
  const {
    manifest,
    spectrum,
    activeLayers,
    toggleLayer,
    setLens,
    activeSceneIndex,
    selectStoryScene,
    frameIndex,
    setFrameIndex,
    storyPlaying,
    setStoryPlaying,
  } = useAppState();

  const scenes: StoryScene[] = manifest?.story_scenes ?? [];
  const currentScene = scenes[activeSceneIndex] || scenes[0];
  const dates = manifest?.event_dates ?? spectrum?.dates ?? [];
  const totalPasses = Math.max(12, dates.length || 12);
  const activeStepColor = STEP_COLORS[activeSceneIndex % STEP_COLORS.length];

  const getSignalStats = (id: SignalId): { text: string; pct: number } => {
    const arr = spectrum?.series?.[id];
    if (!arr || arr.length === 0) return { text: "--", pct: 0 };
    const idx = Math.min(frameIndex, arr.length - 1);
    const val = Number(arr[idx]);
    if (!Number.isFinite(val)) return { text: "--", pct: 0 };
    let minV = Math.min(...arr.map(Number).filter(Number.isFinite));
    let maxV = Math.max(...arr.map(Number).filter(Number.isFinite));
    if (!Number.isFinite(minV) || !Number.isFinite(maxV) || maxV - minV < 1e-4) {
      minV = 0;
      maxV = 1;
    }
    const pct = Math.max(6, Math.min(100, Math.round(((val - minV) / (maxV - minV)) * 100)));
    const text = id === "optical" ? val.toFixed(2) : val.toFixed(1);
    return { text, pct };
  };

  return (
    <div className="domino-dock" aria-label="Domino Sequence and 6 NASA Telemetry Feeds">
      {/* Top Row: Compact Controls + Step Badge + 12-Date Timeline Scrubber (No paragraph walls) */}
      <div className="domino-dock-head">
        <div className="domino-head-left">
          <button
            type="button"
            className={`play-story-btn ${storyPlaying ? "playing" : ""}`}
            onClick={() => setStoryPlaying(!storyPlaying)}
          >
            {storyPlaying ? "⏸ Pause" : "▶ Play Story"}
          </button>
          <span
            className="domino-step-pill"
            style={{
              borderColor: activeStepColor,
              color: activeStepColor,
              backgroundColor: `${activeStepColor}1f`,
            }}
          >
            Step {activeSceneIndex + 1} of {Math.max(1, scenes.length)} ·{" "}
            {currentScene?.phase || "Story"}
          </span>
          <span className="domino-step-title-compact">
            {currentScene?.title || manifest?.target.name || ""}
          </span>
        </div>

        <div className="domino-scrubber">
          <span className="mono scrubber-date-chip">
            {formatCompactDate(dates[frameIndex]) || `Day ${frameIndex + 1}`}
          </span>
          <input
            type="range"
            min={0}
            max={totalPasses - 1}
            value={frameIndex}
            onChange={(e) => setFrameIndex(Number(e.target.value))}
            aria-label="Event timeline date scrubber"
          />
          <span className="mono scrubber-pass-count">
            {frameIndex + 1}/{totalPasses}
          </span>
        </div>
      </div>

      {/* Middle Row: 5-Column Equal Grid of Visual Domino Cards (Zero horizontal clipping) */}
      <div className="domino-chain-track">
        {scenes.slice(0, 5).map((scene, idx) => {
          const isSelected = activeSceneIndex === idx;
          const isPast = idx < activeSceneIndex;
          const stepColor = STEP_COLORS[idx % STEP_COLORS.length];
          const shortDate = formatCompactDate(scene.date_label);
          return (
            <button
              key={scene.index ?? idx}
              type="button"
              style={{ "--step-color": stepColor } as React.CSSProperties}
              className={`domino-card ${isSelected ? "selected" : ""} ${isPast ? "visited" : ""}`}
              onClick={() => selectStoryScene(idx)}
              title={`${scene.title} (${scene.date_label})`}
            >
              <div className="domino-card-top">
                <span className="domino-num" style={{ backgroundColor: isSelected ? stepColor : `${stepColor}33`, color: isSelected ? "#060b16" : stepColor }}>
                  {idx + 1}
                </span>
                <span className="domino-phase" style={{ color: isSelected ? stepColor : undefined }}>
                  {scene.phase}
                </span>
              </div>
              <div className="domino-title">{scene.title}</div>
              <div className="domino-bottom-meta">
                {shortDate && <span className="mono domino-date-chip">{shortDate}</span>}
                <span className="domino-region">
                  {scene.camera?.region_name || manifest?.region_label || ""}
                </span>
              </div>
            </button>
          );
        })}
      </div>

      {/* Bottom Row: 3x2 Telemetry Gauge Buttons for All 6 Equal NASA Datasets */}
      <div className="six-datasets-strip">
        <div className="six-datasets-pills">
          {SIX_NASA_DATASETS.map((ds) => {
            const isActive = activeLayers.includes(ds.id);
            const isPrimary = activeLayers[0] === ds.id;
            const isAiSuggested = currentScene?.active_layers?.includes(ds.id) ?? false;
            const { text, pct } = getSignalStats(ds.id);
            return (
              <button
                key={ds.id}
                type="button"
                className={`dataset-pill ${isActive ? "active" : ""} ${isPrimary ? "primary" : ""}`}
                style={{
                  borderColor: isActive ? ds.color : `${ds.color}40`,
                  backgroundColor: isActive ? `${ds.color}1c` : undefined,
                }}
                onClick={() => {
                  if (!isActive) {
                    toggleLayer(ds.id);
                    setLens(ds.id);
                  } else {
                    setLens(ds.id);
                  }
                }}
                onDoubleClick={() => toggleLayer(ds.id)}
                title={`${ds.shortLabel} (${ds.agency}) — Click to overlay on map, double-click to toggle`}
              >
                <div className="ds-row-top">
                  <span className="ds-left-cluster">
                    <span className="ds-icon" aria-hidden="true">{ds.icon}</span>
                    <span className="ds-name" style={{ color: isActive ? "#fff" : "#e2e8f0" }}>
                      {ds.shortLabel}
                    </span>
                    <span className="ds-sub">{ds.agency}</span>
                  </span>
                  <span className="ds-right-cluster">
                    <span className="ds-val mono" style={{ color: ds.color }}>
                      {text}
                      {ds.unit ? ` ${ds.unit}` : ""}
                    </span>
                    {isAiSuggested && (
                      <span
                        className="ds-ai-tag"
                        style={{ color: ds.color, backgroundColor: `${ds.color}24` }}
                      >
                        AI
                      </span>
                    )}
                  </span>
                </div>
                <div className="ds-gauge-track" aria-hidden="true">
                  <div
                    className="ds-gauge-fill"
                    style={{ width: `${pct}%`, backgroundColor: ds.color }}
                  />
                </div>
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
};
