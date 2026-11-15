import React from "react";
import { AUTO_DEMO_STEPS, TRAINING_TESTS } from "../../content/training";
import { useAppState } from "../../state/store";

export const TrainingDirectorBar: React.FC = () => {
  const {
    trainingPhase,
    autoDemoStep,
    setAutoDemoStep,
    demoPaused,
    setDemoPaused,
    demoDone,
    testChecklist,
    replayTraining,
    skipTraining,
    advanceFromDemoToTest1,
    advanceFromTest1ToTest2,
    graduateToSolo,
  } = useAppState();

  if (trainingPhase === "solo") return null;

  if (trainingPhase === "round1-demo") {
    const activeScript = AUTO_DEMO_STEPS[autoDemoStep];
    return (
      <section className="training-bar" aria-label="Training Round 1 Automatic Demo">
        <div className="training-bar-head">
          <div>
            <div className="tutorial-kicker">
              Training · Round 1 of 2 (Automatic Demo · Real Target #1: Barnard&apos;s Star)
            </div>
            <h1 className="panel-title" style={{ fontSize: "1.12rem", marginTop: "0.2rem" }}>
              Watch First: How Citizen Scientists Spot Hidden Worlds in SPHEREx Scans
            </h1>
          </div>

          <div style={{ display: "flex", gap: "0.45rem", flexWrap: "wrap", alignItems: "center" }}>
            {!demoDone && (
              <button
                type="button"
                className="btn"
                onClick={() => setDemoPaused(!demoPaused)}
              >
                {demoPaused ? "Resume Auto" : "Pause Auto"}
              </button>
            )}
            <button type="button" className="btn" onClick={replayTraining}>
              Replay Demo
            </button>
            <button
              type="button"
              className="btn btn-primary"
              onClick={advanceFromDemoToTest1}
            >
              {demoDone ? "Start Round 2: Hands-On Test (2 Targets) ->" : "Skip to Round 2 ->"}
            </button>
            <button type="button" className="btn btn-ghost" onClick={skipTraining}>
              Skip Training
            </button>
          </div>
        </div>

        <div className="clue-strip" aria-label="Three sky clues">
          <span className="clue-chip cyan">Red + Cyan Pair = It Moved</span>
          <span className="clue-chip amber">Bright Only in Cold Glow (4.5 &mu;m) = Cold ~250 K World</span>
          <span className="clue-chip emerald">Same Spot Brightens/Dims = Flickering Star</span>
        </div>

        <div className="tutorial-progress" style={{ marginTop: "0.65rem", marginBottom: "0.65rem" }}>
          {AUTO_DEMO_STEPS.map((s) => (
            <button
              key={s.step}
              type="button"
              className={`tutorial-step-dot ${
                s.step === autoDemoStep ? "active" : s.step < autoDemoStep ? "done" : ""
              }`}
              onClick={() => {
                setDemoPaused(true);
                setAutoDemoStep(s.step);
              }}
            >
              {s.title}
            </button>
          ))}
        </div>

        <div className={`callout-box ${demoDone ? "callout-success" : ""}`}>
          <strong>{demoDone ? "Demo Complete:" : `Auto-Showing (${autoDemoStep + 1}/4):`}</strong>{" "}
          {activeScript.narration}
        </div>
      </section>
    );
  }

  // Round 2: Hands-On Check 1 of 2 (WISE 0855) & Check 2 of 2 (RW Aurigae)
  const spec = TRAINING_TESTS[trainingPhase];
  const step3Done = testChecklist.testPassed;

  return (
    <section className="training-bar training-test-bar" aria-label={`Training Round 2 Check ${spec.testNumber} of 2`}>
      <div className="training-bar-head">
        <div>
          <div className="tutorial-kicker" style={{ color: "var(--accent-amber)" }}>
            Training · Round 2 of 2 · Practical Check {spec.testNumber} of 2 (Real Example: {spec.targetName})
          </div>
          <h1 className="panel-title" style={{ fontSize: "1.12rem", marginTop: "0.2rem" }}>
            Your Turn: Inspect {spec.targetName} &amp; Show What You Learned
          </h1>
          <p style={{ margin: "0.25rem 0 0", fontSize: "0.83rem", color: "var(--text-secondary)" }}>
            {spec.prompt}
          </p>
        </div>

        <div style={{ display: "flex", gap: "0.45rem", flexWrap: "wrap", alignItems: "center" }}>
          <button type="button" className="btn" onClick={replayTraining}>
            Rewatch Round 1 Demo
          </button>
          <button type="button" className="btn btn-ghost" onClick={skipTraining}>
            Skip Training
          </button>
        </div>
      </div>

      <div className="test-checklist-grid">
        <div className={`test-step-pill ${testChecklist.action1Done ? "done" : "pending"}`}>
          <span className="mono">{testChecklist.action1Done ? "✓" : "○"}</span>
          <span>{spec.action1Label}</span>
        </div>
        <div className={`test-step-pill ${testChecklist.action2Done ? "done" : "pending"}`}>
          <span className="mono">{testChecklist.action2Done ? "✓" : "○"}</span>
          <span>{spec.action2Label}</span>
        </div>
        <div className={`test-step-pill ${step3Done ? "done" : "pending"}`}>
          <span className="mono">{step3Done ? "✓" : "○"}</span>
          <span>{spec.action3Label}</span>
        </div>
      </div>

      {testChecklist.feedback && (
        <div
          className={`callout-box ${testChecklist.feedback.ok ? "callout-success" : "callout-warn"}`}
          style={{
            marginTop: "0.65rem",
            display: "flex",
            flexWrap: "wrap",
            justifyContent: "space-between",
            alignItems: "center",
            gap: "0.65rem",
          }}
        >
          <span>{testChecklist.feedback.text}</span>
          {testChecklist.testPassed && (
            <button
              type="button"
              className="btn btn-primary"
              onClick={
                trainingPhase === "round2-test1" ? advanceFromTest1ToTest2 : graduateToSolo
              }
            >
              {trainingPhase === "round2-test1"
                ? "Next: Check 2 of 2 (RW Aurigae) ->"
                : "Open Remaining Solo Examples ->"}
            </button>
          )}
        </div>
      )}
    </section>
  );
};
