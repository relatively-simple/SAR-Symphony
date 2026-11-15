import React, { useState } from "react";
import { useAppState } from "../../state/store";
import { Spinner } from "../common/Spinner";

const STEP_NODES = [
  { color: "#f97316", icon: "🌡️", short: "Heat" },
  { color: "#14b8a6", icon: "💨", short: "Wind" },
  { color: "#3b82f6", icon: "🌧️", short: "Rain" },
  { color: "#a855f7", icon: "📡", short: "SAR" },
  { color: "#f43f5e", icon: "💡", short: "Impact" },
];

const HOTSPOT_ACCENTS: Record<string, string> = {
  onset: "#f97316",
  peak_impact: "#a855f7",
  blackout: "#eab308",
  illusion: "#10b981",
};

const QUICK_CHIPS = [
  { label: "⚡ Sequence", prompt: "Why did these datasets change in this sequence?" },
  { label: "🌊 Upwind Cause", prompt: "What triggered this disaster upwind?" },
  { label: "🛡️ Radar Guard", prompt: "How does Illusion Guard prevent false radar conclusions?" },
];

export const PatternFinderCard: React.FC = () => {
  const {
    manifest,
    activeSceneIndex,
    selectStoryScene,
    aiExplanation,
    aiLoading,
    askAiDirector,
    patterns,
    activePatternId,
    selectPattern,
  } = useAppState();

  const [question, setQuestion] = useState("");
  const [showAnswerDrawer, setShowAnswerDrawer] = useState(false);

  const scenes = manifest?.story_scenes ?? [];
  const activeScene = scenes[activeSceneIndex] ?? scenes[0] ?? null;
  const activeLink = activeScene?.causal_chain?.[0] ?? null;
  const candidates = patterns?.candidates ?? [];
  const stepColor = STEP_NODES[activeSceneIndex % STEP_NODES.length].color;
  const corrPct = activeLink ? Math.min(100, Math.round(Math.abs(activeLink.correlation) * 100)) : 75;

  const handleAsk = (e: React.FormEvent) => {
    e.preventDefault();
    if (!question.trim()) return;
    setShowAnswerDrawer(true);
    void askAiDirector(question.trim());
  };

  const handleQuickChip = (prompt: string) => {
    setQuestion(prompt);
    setShowAnswerDrawer(true);
    void askAiDirector(prompt);
  };

  return (
    <section className="panel-card causal-card" aria-label="Visual Cause-to-Effect Diagram">
      {/* Compact Header */}
      <div className="panel-header-compact">
        <div className="panel-head-text">
          <h2 className="panel-title-sm">⚡ Cause → Effect Diagram</h2>
          <div className="panel-sub-sm">
            {manifest?.category || "Earth Event"} · {manifest?.target.name || "Loading..."}
          </div>
        </div>
        <span
          className="mode-badge mono"
          style={{ borderColor: `${stepColor}80`, color: stepColor }}
        >
          {aiExplanation?.mode === "gemini_enhanced" ? "✨ Gemini" : "⚡ Live Graph"}
        </span>
      </div>

      {/* 1. Interactive 5-Node Domino Flow SVG Pipeline */}
      <div className="causal-pipeline-diagram" role="group" aria-label="5-step causal flow">
        {scenes.slice(0, 5).map((sc, idx) => {
          const node = STEP_NODES[idx % STEP_NODES.length];
          const isActive = idx === activeSceneIndex;
          const isPast = idx < activeSceneIndex;
          return (
            <React.Fragment key={sc.index ?? idx}>
              <button
                type="button"
                className={`pipeline-node ${isActive ? "active" : ""} ${isPast ? "past" : ""}`}
                style={{
                  borderColor: isActive || isPast ? node.color : undefined,
                  backgroundColor: isActive ? `${node.color}28` : undefined,
                  boxShadow: isActive ? `0 0 12px ${node.color}55` : undefined,
                }}
                onClick={() => selectStoryScene(idx)}
                title={`${idx + 1}. ${sc.phase}: ${sc.title}`}
              >
                <span className="pn-icon" aria-hidden="true">{node.icon}</span>
                <span className="pn-label" style={{ color: isActive ? "#fff" : node.color }}>
                  {node.short}
                </span>
              </button>
              {idx < Math.min(5, scenes.length) - 1 && (
                <div
                  className="pipeline-bridge"
                  style={{
                    background: isPast
                      ? `linear-gradient(90deg, ${node.color}, ${STEP_NODES[(idx + 1) % 5].color})`
                      : undefined,
                  }}
                  aria-hidden="true"
                />
              )}
            </React.Fragment>
          );
        })}
      </div>

      {/* 2. Visual Cause -> Effect Coupling Bridge */}
      {activeLink && (
        <div className="causal-bridge-card" style={{ borderLeftColor: stepColor }}>
          <div className="bridge-nodes-row">
            <div className="bridge-node cause-node">
              <span className="bn-tag">CAUSE</span>
              <span className="bn-name">{activeLink.from_signal}</span>
            </div>

            <div className="bridge-vector">
              <span className="bv-lag mono">
                {activeLink.lag_hours > 0 ? `+${activeLink.lag_hours}h` : "0h"}
              </span>
              <div className="bv-arrow-line" aria-hidden="true">
                <span className="bv-arrow-head">▶</span>
              </div>
              <div className="bv-corr-wrap">
                <div className="bv-corr-track">
                  <div
                    className="bv-corr-fill"
                    style={{ width: `${corrPct}%`, backgroundColor: stepColor }}
                  />
                </div>
                <span className="bv-corr-label mono">r={activeLink.correlation.toFixed(2)}</span>
              </div>
            </div>

            <div className="bridge-node effect-node">
              <span className="bn-tag">EFFECT</span>
              <span className="bn-name">{activeLink.to_signal}</span>
            </div>
          </div>

          <div className="causal-link-one-liner">{activeLink.explanation}</div>
        </div>
      )}

      {/* 3. 2x2 Color-Coded Map Hotspots */}
      {candidates.length > 0 && (
        <div className="hotspot-pills-row">
          {candidates.slice(0, 4).map((cand) => {
            const isSel = activePatternId === cand.id;
            const accent = HOTSPOT_ACCENTS[cand.kind] || "#38bdf8";
            return (
              <button
                key={cand.id}
                type="button"
                className={`hotspot-pill ${isSel ? "active" : ""}`}
                style={{
                  borderColor: isSel ? accent : `${accent}50`,
                  backgroundColor: isSel ? `${accent}1e` : undefined,
                }}
                onClick={() => selectPattern(cand)}
                title={cand.summary}
              >
                <span className="hp-top">
                  <span className="hp-dot" style={{ backgroundColor: accent }} aria-hidden="true" />
                  <span className="hp-label">{cand.suggested_label}</span>
                </span>
                <span className="hp-coord mono">
                  {cand.dec.toFixed(2)}°, {cand.ra.toFixed(2)}°
                </span>
              </button>
            );
          })}
        </div>
      )}

      {/* 4. Compact AI Chips & On-Demand Ask AI Drawer */}
      <div className="ai-compact-controls">
        <div className="ai-quick-chips">
          {QUICK_CHIPS.map((c) => (
            <button
              key={c.label}
              type="button"
              className="chip-btn"
              onClick={() => handleQuickChip(c.prompt)}
            >
              {c.label}
            </button>
          ))}
        </div>

        <form onSubmit={handleAsk} className="ai-ask-form">
          <input
            type="text"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="Ask AI why..."
            aria-label="Ask AI Causal Director"
          />
          <button type="submit" className="btn btn-coral btn-xs" disabled={aiLoading}>
            Ask AI
          </button>
        </form>
      </div>

      {/* Expandable concise AI Answer Drawer (Hidden by default to keep visuals front & center) */}
      {showAnswerDrawer && (
        <div className="ai-popover-answer" role="region" aria-label="AI explanation">
          <div className="ai-pop-head">
            <span className="mono">AI Causal Insight</span>
            <button
              type="button"
              className="ai-pop-close"
              onClick={() => setShowAnswerDrawer(false)}
              aria-label="Close AI explanation"
            >
              ✕
            </button>
          </div>
          {aiLoading ? (
            <Spinner label="Computing couplings..." />
          ) : aiExplanation ? (
            <p className="ai-answer-clamped">{aiExplanation.answer}</p>
          ) : null}
        </div>
      )}
    </section>
  );
};
