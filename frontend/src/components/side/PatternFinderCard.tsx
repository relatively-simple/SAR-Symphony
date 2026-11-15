import React, { useMemo } from "react";
import type { PatternCandidate } from "../../api/types";
import { useAppState } from "../../state/store";

const KIND_LABELS: Record<string, string> = {
  mover: "Moving Object",
  variable: "Brightness Change",
  cold_ir: "Cold Heat Peak",
  archive_drift: "15-Yr Sky Shift",
};

const CHOICE_BUTTONS = [
  { id: "mover", label: "Moving World" },
  { id: "variable", label: "Flickering Star" },
  { id: "cold_ir", label: "Cold Heat World" },
  { id: "artifact", label: "Noise / Artifact" },
];

export const PatternFinderCard: React.FC = () => {
  const {
    manifest,
    patterns,
    patternsLoading,
    activePatternId,
    selectPattern,
    submitVerdict,
    verdicts,
  } = useAppState();

  const selected: PatternCandidate | null = useMemo(() => {
    if (!patterns || patterns.candidates.length === 0) return null;
    return (
      patterns.candidates.find((c) => c.id === activePatternId) ?? patterns.candidates[0]
    );
  }, [patterns, activePatternId]);

  const verdictKey =
    manifest && selected ? `${manifest.session_id}:${selected.id}` : null;
  const savedVerdict = verdictKey ? verdicts[verdictKey] ?? null : null;

  return (
    <section className="panel-card pattern-card" aria-label="Automated Pattern Finder">
      <div className="panel-header" style={{ marginBottom: "0.45rem" }}>
        <div>
          <h2 className="panel-title">Auto Pattern Finder</h2>
          <div style={{ fontSize: "0.74rem", color: "var(--text-muted)" }}>
            Scans the real SPHEREx infrared cube so you don&apos;t have to hunt blindly
          </div>
        </div>
        {patterns && (
          <span className="status-pill" style={{ color: "var(--accent-cyan)", fontWeight: 700 }}>
            {patterns.n_patterns} {patterns.n_patterns === 1 ? "clue" : "clues"} found
          </span>
        )}
      </div>

      {patternsLoading ? (
        <div style={{ fontSize: "0.82rem", color: "var(--text-muted)" }}>
          Scanning multi-band image stack for movers, thermal heat peaks, and flickers...
        </div>
      ) : !patterns || patterns.candidates.length === 0 ? (
        <div className="callout-box">
          {patterns?.summary ?? "No strong >4.5σ moving pairs or thermal excess candidates detected here."}
        </div>
      ) : (
        <>
          <div className="pattern-pills">
            {patterns.candidates.map((cand, idx) => {
              const isSelected = selected?.id === cand.id;
              const isReviewed = Boolean(manifest && verdicts[`${manifest.session_id}:${cand.id}`]);
              return (
                <button
                  key={cand.id}
                  type="button"
                  className={`pattern-pill ${isSelected ? "active" : ""}`}
                  onClick={() => selectPattern(cand)}
                >
                  <span className="mono">#{idx + 1}</span>
                  <span>{KIND_LABELS[cand.kind] ?? cand.kind}</span>
                  {isReviewed && <span style={{ color: "var(--accent-emerald)" }}>&#10003;</span>}
                </button>
              );
            })}
          </div>

          {selected && (
            <div className="pattern-detail-box">
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: "0.5rem" }}>
                <strong style={{ fontSize: "0.9rem", color: "var(--text-primary)" }}>
                  {selected.title}
                </strong>
                <span className="status-pill mono">
                  {selected.confidence} · {selected.snr.toFixed(1)}&sigma;
                </span>
              </div>

              <p style={{ margin: "0.35rem 0 0.55rem", fontSize: "0.81rem", color: "var(--text-secondary)" }}>
                {selected.summary}
              </p>

              <div className="verdict-bar">
                <div style={{ fontSize: "0.73rem", color: "var(--text-muted)", marginBottom: "0.35rem" }}>
                  Verify what you see on the image to score Discovery Points:
                </div>
                <div style={{ display: "flex", flexWrap: "wrap", gap: "0.35rem" }}>
                  {CHOICE_BUTTONS.map((btn) => {
                    const chosen = savedVerdict?.choice === btn.id;
                    return (
                      <button
                        key={btn.id}
                        type="button"
                        className={`detector-chip ${chosen ? "active" : ""}`}
                        onClick={() => submitVerdict(selected, btn.id)}
                      >
                        {btn.label}
                      </button>
                    );
                  })}
                </div>
              </div>

              {savedVerdict && (
                <div
                  className={`callout-box ${savedVerdict.matched ? "callout-success" : ""}`}
                  style={{ marginTop: "0.55rem", fontSize: "0.78rem" }}
                >
                  {savedVerdict.matched
                    ? `Verified! Matches our pixel measurement (${selected.suggested_label}) — +${savedVerdict.points} Discovery Points logged!`
                    : `Logged (+${savedVerdict.points} pts)! Note: pixel measurements suggest "${selected.suggested_label}" here — toggle Side-by-Side or Cold Heat to double check.`}
                </div>
              )}
            </div>
          )}
        </>
      )}
    </section>
  );
};
