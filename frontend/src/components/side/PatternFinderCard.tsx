import React from "react";
import { TRAINING_TESTS } from "../../content/training";
import { useAppState } from "../../state/store";

const CHOICE_BUTTONS = [
  { id: "mover", label: "Moving World" },
  { id: "variable", label: "Flickering Star" },
  { id: "cold_ir", label: "Cold Heat World" },
  { id: "artifact", label: "Static / Artifact" },
];

export const PatternFinderCard: React.FC = () => {
  const {
    manifest,
    trainingPhase,
    autoDemoStep,
    demoDone,
    testChecklist,
    submitTrainingVerdict,
    submitSoloVerdict,
    verdicts,
    patterns,
    patternsLoading,
    activePatternId,
    selectPattern,
    soloRevealOverride,
    toggleSoloReveal,
    advanceFromDemoToTest1,
    advanceFromTest1ToTest2,
    graduateToSolo,
  } = useAppState();

  // 1. ROUND 1: AUTOMATIC DEMO READOUT
  if (trainingPhase === "round1-demo") {
    const highlighted = autoDemoStep >= 3;
    return (
      <section className="panel-card pattern-card" aria-label="Round 1 Automatic Classification">
        <div className="panel-header" style={{ marginBottom: "0.45rem" }}>
          <div>
            <h2 className="panel-title">Auto Demo: Inspect &amp; Classify</h2>
            <div style={{ fontSize: "0.74rem", color: "var(--text-muted)" }}>
              Watch how we confirm a pattern on Barnard&apos;s Star
            </div>
          </div>
          <span className="status-pill" style={{ color: "var(--accent-cyan)", fontWeight: 700 }}>
            {demoDone ? "+25 pts Demo" : `Step ${autoDemoStep + 1}/4`}
          </span>
        </div>

        <div style={{ display: "flex", flexWrap: "wrap", gap: "0.38rem", marginBottom: "0.6rem" }}>
          {CHOICE_BUTTONS.map((btn) => (
            <button
              key={btn.id}
              type="button"
              disabled
              className={`detector-chip ${highlighted && btn.id === "mover" ? "active" : ""}`}
            >
              {btn.label}
              {highlighted && btn.id === "mover" ? " ✓" : ""}
            </button>
          ))}
        </div>

        {highlighted ? (
          <div className="callout-box callout-success" style={{ fontSize: "0.8rem" }}>
            <strong>Demo Classification: Moving World (+25 pts)</strong>
            <div style={{ marginTop: "0.25rem" }}>
              Red &apos;now&apos; sat ~25&quot; north of Cyan &apos;before&apos; in Difference Only,
              and clicking it plotted a bright cool red dwarf spectrum.
            </div>
            <button
              type="button"
              className="btn btn-primary"
              style={{ marginTop: "0.55rem", width: "100%" }}
              onClick={advanceFromDemoToTest1}
            >
              Start Round 2: Hands-On Check (2 Targets) &rarr;
            </button>
          </div>
        ) : (
          <div className="callout-box" style={{ fontSize: "0.8rem" }}>
            Demonstrating automatic comparison &amp; spectrum click first — verdict will be shown on
            Step 4/4.
          </div>
        )}
      </section>
    );
  }

  // 2. ROUND 2: HANDS-ON SKILL TEST (NO SPOILERS!)
  if (trainingPhase === "round2-test1" || trainingPhase === "round2-test2") {
    const spec = TRAINING_TESTS[trainingPhase];
    const checksReady = testChecklist.action1Done && testChecklist.action2Done;

    return (
      <section className="panel-card pattern-card" aria-label={`Training Check ${spec.testNumber} Verdict`}>
        <div className="panel-header" style={{ marginBottom: "0.45rem" }}>
          <div>
            <h2 className="panel-title">
              Check {spec.testNumber} of 2: Classify {spec.targetName}
            </h2>
            <div style={{ fontSize: "0.74rem", color: "var(--text-muted)" }}>
              Complete viewer Steps 1 &amp; 2 first, then select what you found
            </div>
          </div>
          <span
            className="status-pill"
            style={{
              color: testChecklist.testPassed ? "var(--accent-emerald)" : "var(--accent-amber)",
              fontWeight: 700,
            }}
          >
            {testChecklist.testPassed ? "Passed (+50 pts)" : checksReady ? "Ready to Classify" : "Inspect Image First"}
          </span>
        </div>

        <div style={{ display: "flex", flexWrap: "wrap", gap: "0.4rem" }}>
          {CHOICE_BUTTONS.map((btn) => {
            const isSolvedBtn = testChecklist.testPassed && btn.id === spec.expectedKind;
            return (
              <button
                key={btn.id}
                type="button"
                disabled={testChecklist.testPassed}
                className={`detector-chip ${isSolvedBtn ? "active" : ""}`}
                onClick={() => submitTrainingVerdict(btn.id)}
              >
                {btn.label}
              </button>
            );
          })}
        </div>

        {!checksReady && !testChecklist.testPassed && (
          <div className="callout-box" style={{ marginTop: "0.6rem", fontSize: "0.78rem" }}>
            Waiting for you to inspect the viewer above: complete Steps 1 &amp; 2 so we verify
            you checked the image pixels &amp; spectrum!
          </div>
        )}

        {testChecklist.testPassed && (
          <div className="callout-box callout-success" style={{ marginTop: "0.6rem", fontSize: "0.8rem" }}>
            <div>{spec.successNote}</div>
            <button
              type="button"
              className="btn btn-primary"
              style={{ marginTop: "0.55rem", width: "100%" }}
              onClick={
                trainingPhase === "round2-test1" ? advanceFromTest1ToTest2 : graduateToSolo
              }
            >
              {trainingPhase === "round2-test1"
                ? "Continue to Check 2 of 2 (RW Aurigae) ->"
                : "Enter Solo Discovery Mode (No Hints) ->"}
            </button>
          </div>
        )}
      </section>
    );
  }

  // 3. SOLO MODE: UNASSISTED CITIZEN DISCOVERY LOG (NO TUTORIAL HINTS / NO PRE-SPOILERS!)
  const saved = manifest ? verdicts[manifest.session_id] : undefined;
  const isRevealed = Boolean(saved || soloRevealOverride);

  return (
    <section className="panel-card pattern-card" aria-label="Citizen Discovery Log">
      <div className="panel-header" style={{ marginBottom: "0.45rem" }}>
        <div>
          <h2 className="panel-title">Your Discovery Log</h2>
          <div style={{ fontSize: "0.74rem", color: "var(--text-muted)" }}>
            Inspect freely on your own, then log what this field contains
          </div>
        </div>
        {saved && (
          <span className="status-pill" style={{ color: "var(--accent-emerald)", fontWeight: 700 }}>
            Logged +{saved.points} pts
          </span>
        )}
      </div>

      <div style={{ display: "flex", flexWrap: "wrap", gap: "0.4rem" }}>
        {CHOICE_BUTTONS.map((btn) => {
          const isChosen = saved?.choice === btn.id;
          return (
            <button
              key={btn.id}
              type="button"
              disabled={Boolean(saved)}
              className={`detector-chip ${isChosen ? "active" : ""}`}
              onClick={() => submitSoloVerdict(btn.id)}
            >
              {btn.label}
            </button>
          );
        })}
      </div>

      {saved && (
        <div
          className={`callout-box ${saved.matched ? "callout-success" : ""}`}
          style={{ marginTop: "0.6rem", fontSize: "0.8rem" }}
        >
          {saved.matched
            ? `Logged (+${saved.points} pts)! Matches quantitative SPHEREx pixel measurements (${saved.expectedSummary}).`
            : `Observation logged (+${saved.points} pts). Quantitative pixel analysis detects: ${saved.expectedSummary}.`}
        </div>
      )}

      {!saved && (
        <div style={{ marginTop: "0.55rem", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <button
            type="button"
            className="btn btn-ghost"
            style={{ fontSize: "0.74rem", padding: "0.25rem 0.55rem" }}
            onClick={toggleSoloReveal}
          >
            {soloRevealOverride ? "Hide Pixel Math Check" : "Compare vs Pixel Math"}
          </button>
        </div>
      )}

      {isRevealed && (
        <div style={{ marginTop: "0.65rem", borderTop: "1px solid var(--border-subtle)", paddingTop: "0.6rem" }}>
          <div style={{ fontSize: "0.73rem", fontWeight: 700, color: "var(--text-muted)", marginBottom: "0.4rem" }}>
            QUANTITATIVE PIXEL CROSS-CHECK
          </div>
          {patternsLoading ? (
            <div style={{ fontSize: "0.78rem", color: "var(--text-muted)" }}>Checking pixels...</div>
          ) : !patterns || patterns.candidates.length === 0 ? (
            <div style={{ fontSize: "0.78rem", color: "var(--text-secondary)" }}>
              No &gt;4.5&sigma; moving dipole or strong thermal anomaly detected above background noise.
            </div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: "0.4rem" }}>
              <div className="pattern-pills" style={{ marginBottom: 0 }}>
                {patterns.candidates.map((cand, idx) => (
                  <button
                    key={cand.id}
                    type="button"
                    className={`pattern-pill ${activePatternId === cand.id ? "active" : ""}`}
                    onClick={() => selectPattern(cand)}
                  >
                    <span className="mono">#{idx + 1}</span>
                    <span>{cand.title}</span>
                  </button>
                ))}
              </div>
              {(() => {
                const c =
                  patterns.candidates.find((x) => x.id === activePatternId) ??
                  patterns.candidates[0];
                return c ? (
                  <div style={{ fontSize: "0.77rem", color: "var(--text-secondary)" }}>
                    {c.summary} ({c.snr.toFixed(1)}&sigma;)
                  </div>
                ) : null;
              })()}
            </div>
          )}
        </div>
      )}
    </section>
  );
};
