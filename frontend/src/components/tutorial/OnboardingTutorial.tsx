import React, { useEffect, useState } from "react";
import { useAppState } from "../../state/store";

type DemoMode = "past" | "present" | "diff";

const STATIC_STARS = [
  { x: 2, y: 2, flux: 0.85 },
  { x: 7, y: 2, flux: 0.7 },
  { x: 1, y: 7, flux: 0.65 },
  { x: 8, y: 8, flux: 0.9 },
];

const MOVER_PAST = { x: 4, y: 5 };
const MOVER_PRESENT = { x: 6, y: 4 };

const PRACTICE_STARS = [
  { x: 2, y: 2 },
  { x: 8, y: 2 },
  { x: 2, y: 8 },
  { x: 7, y: 7 },
];
const PRACTICE_MOVER_PAST = { x: 4, y: 6 };
const PRACTICE_MOVER_PRESENT = { x: 5, y: 3 };

export const OnboardingTutorial: React.FC = () => {
  const { tutorialOpen, setTutorialOpen, completeTutorial } = useAppState();
  const [step, setStep] = useState(0);
  const [demoMode, setDemoMode] = useState<DemoMode>("past");

  // Step 4 interactive mini-challenge state
  const [practicePhase, setPracticePhase] = useState<"past" | "present" | "diff">("past");
  const [blinkActive, setBlinkActive] = useState(true);
  const [practiceHint, setPracticeHint] = useState<string | null>(null);
  const [practiceSolved, setPracticeSolved] = useState(false);

  useEffect(() => {
    if (!tutorialOpen || step !== 3 || !blinkActive || practicePhase === "diff") return;
    const id = window.setInterval(() => {
      setPracticePhase((prev) => (prev === "past" ? "present" : "past"));
    }, 850);
    return () => window.clearInterval(id);
  }, [tutorialOpen, step, blinkActive, practicePhase]);

  if (!tutorialOpen) return null;

  const handlePracticeClick = (gx: number, gy: number) => {
    const nearNow = Math.hypot(gx - PRACTICE_MOVER_PRESENT.x, gy - PRACTICE_MOVER_PRESENT.y) <= 1.1;
    const nearOld = Math.hypot(gx - PRACTICE_MOVER_PAST.x, gy - PRACTICE_MOVER_PAST.y) <= 1.1;
    if (nearNow || nearOld) {
      setPracticeSolved(true);
      setPracticeHint(
        "Spot on! Stationary background stars stayed frozen and canceled to zero — you caught the object that moved between Past and Present (+50 pts)!"
      );
      return;
    }
    setPracticeHint(
      "That star stayed fixed in both Past and Present. Hint: click 'Difference Only' or watch which ONE dot actually hops!"
    );
  };

  return (
    <div
      className="modal-backdrop"
      role="dialog"
      aria-modal="true"
      aria-label="Citizen Scientist Onboarding Tutorial"
    >
      <div className="modal-card tutorial-modal">
        <div className="tutorial-header">
          <div>
            <div className="tutorial-kicker">
              NASA Space Apps · SPHEREx Citizen Scientist Boot Camp
            </div>
            <h2 className="panel-title" style={{ fontSize: "1.22rem", marginTop: "0.15rem" }}>
              {step === 0 && "1. What Are We Looking For? (In Plain English)"}
              {step === 1 && "2. Spot the Difference: Past vs Present"}
              {step === 2 && "3. No More Confusing 'Random Colours'"}
              {step === 3 && "4. Quick Practice: Catch the Moving World (+50 pts)"}
            </h2>
          </div>

          <button
            type="button"
            className="btn btn-ghost"
            onClick={() => {
              completeTutorial(false);
            }}
          >
            Skip Tutorial &rarr;
          </button>
        </div>

        {/* Step progress strip */}
        <div className="tutorial-progress" aria-label={`Step ${step + 1} of 4`}>
          {[0, 1, 2, 3].map((i) => (
            <button
              key={i}
              type="button"
              className={`tutorial-step-dot ${i === step ? "active" : i < step ? "done" : ""}`}
              onClick={() => setStep(i)}
            >
              Step {i + 1}
            </button>
          ))}
        </div>

        {/* STEP 1 */}
        {step === 0 && (
          <div className="tutorial-body">
            <p className="tutorial-lead">
              NASA&apos;s <strong>SPHEREx</strong> space telescope photographs the entire sky over
              multiple months (2025, 2026...) in <strong>102 infrared colors</strong>. Hidden
              worlds like <em>Planet X</em> or nearby brown dwarfs are too cold and faint for normal
              cameras — so we catch them using three simple clues:
            </p>

            <div className="tutorial-cards-3">
              <div className="tutorial-mini-card">
                <div className="tutorial-badge cyan">Clue 1 · It Moves</div>
                <h3>Past &rarr; Present Shift</h3>
                <p>
                  Distant stars stay completely frozen from 2025 to 2026. Anything close to Earth
                  hops slightly across the sky between scans.
                </p>
              </div>
              <div className="tutorial-mini-card">
                <div className="tutorial-badge amber">Clue 2 · Cold Heat Glow</div>
                <h3>Invisible in Normal Light</h3>
                <p>
                  Cold ~250 K planets shine brightly only in long thermal infrared (3.8–5.0 &mu;m)
                  even when optical star maps like Gaia see nothing there.
                </p>
              </div>
              <div className="tutorial-mini-card">
                <div className="tutorial-badge emerald">Clue 3 · Flickers in Place</div>
                <h3>Variable Brightness</h3>
                <p>
                  Pulsating giants or dust-eclipsed young stars grow brighter and dimmer without
                  changing sky coordinates.
                </p>
              </div>
            </div>
          </div>
        )}

        {/* STEP 2 */}
        {step === 1 && (
          <div className="tutorial-body">
            <p className="tutorial-lead">
              Instead of guessing from raw images, compare <strong>PAST</strong> against{" "}
              <strong>PRESENT</strong>, or subtract them so <strong>only changes remain</strong>:
            </p>

            <div className="tutorial-demo-split">
              <div className="tutorial-demo-canvas-wrap">
                <svg viewBox="0 0 100 100" className="tutorial-svg-box">
                  <rect width="100" height="100" fill="#060913" rx="6" />
                  {demoMode !== "diff" &&
                    STATIC_STARS.map((s, idx) => (
                      <circle
                        key={idx}
                        cx={s.x * 10 + 5}
                        cy={s.y * 10 + 5}
                        r={3.8}
                        fill="#fde68a"
                        opacity={s.flux}
                      />
                    ))}

                  {demoMode === "past" && (
                    <circle
                      cx={MOVER_PAST.x * 10 + 5}
                      cy={MOVER_PAST.y * 10 + 5}
                      r={4.2}
                      fill="#7dd3fc"
                    />
                  )}
                  {demoMode === "present" && (
                    <circle
                      cx={MOVER_PRESENT.x * 10 + 5}
                      cy={MOVER_PRESENT.y * 10 + 5}
                      r={4.2}
                      fill="#fbbf24"
                    />
                  )}
                  {demoMode === "diff" && (
                    <>
                      <line
                        x1={MOVER_PAST.x * 10 + 5}
                        y1={MOVER_PAST.y * 10 + 5}
                        x2={MOVER_PRESENT.x * 10 + 5}
                        y2={MOVER_PRESENT.y * 10 + 5}
                        stroke="#94a3b8"
                        strokeWidth="1.2"
                        strokeDasharray="2 2"
                      />
                      <circle
                        cx={MOVER_PAST.x * 10 + 5}
                        cy={MOVER_PAST.y * 10 + 5}
                        r={4.4}
                        fill="#22d3ee"
                      />
                      <text
                        x={MOVER_PAST.x * 10 + 5}
                        y={MOVER_PAST.y * 10 + 13}
                        fill="#22d3ee"
                        fontSize="5"
                        textAnchor="middle"
                      >
                        WAS HERE
                      </text>
                      <circle
                        cx={MOVER_PRESENT.x * 10 + 5}
                        cy={MOVER_PRESENT.y * 10 + 5}
                        r={4.4}
                        fill="#fb7185"
                      />
                      <text
                        x={MOVER_PRESENT.x * 10 + 5}
                        y={MOVER_PRESENT.y * 10 - 3}
                        fill="#fb7185"
                        fontSize="5"
                        textAnchor="middle"
                      >
                        MOVED HERE
                      </text>
                    </>
                  )}
                </svg>

                <div className="tutorial-demo-controls">
                  <button
                    type="button"
                    className={`lens-pill ${demoMode === "past" ? "active" : ""}`}
                    onClick={() => setDemoMode("past")}
                  >
                    1. PAST Scan
                  </button>
                  <button
                    type="button"
                    className={`lens-pill ${demoMode === "present" ? "active" : ""}`}
                    onClick={() => setDemoMode("present")}
                  >
                    2. PRESENT Scan
                  </button>
                  <button
                    type="button"
                    className={`lens-pill ${demoMode === "diff" ? "active" : ""}`}
                    onClick={() => setDemoMode("diff")}
                  >
                    3. DIFFERENCE ONLY
                  </button>
                </div>
              </div>

              <div className="tutorial-demo-notes">
                <div className="callout-box">
                  <strong>Why Subtraction Works:</strong>
                  <p style={{ margin: "0.35rem 0 0" }}>
                    The 4 yellow background stars never moved, so <code>Present &minus; Past = 0</code>.
                    They completely erase into pitch-black space!
                  </p>
                </div>
                <div className="callout-box" style={{ borderLeftColor: "var(--accent-rose)" }}>
                  <strong>Red + Cyan Side-by-Side = MOVER!</strong>
                  <p style={{ margin: "0.35rem 0 0" }}>
                    <span style={{ color: "#22d3ee", fontWeight: 700 }}>Cyan</span> marks where
                    the object <em>used to sit</em>.{" "}
                    <span style={{ color: "#fb7185", fontWeight: 700 }}>Red</span> marks where it{" "}
                    <em>moved today</em>.
                  </p>
                </div>
                <div className="callout-box" style={{ borderLeftColor: "var(--accent-amber)" }}>
                  <strong>Single Dot Alone = VARIABLE!</strong>
                  <p style={{ margin: "0.35rem 0 0" }}>
                    If a star got brighter or dimmer without moving, you see one spot alone in the
                    same coordinate.
                  </p>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* STEP 3 */}
        {step === 2 && (
          <div className="tutorial-body">
            <p className="tutorial-lead">
              You don&apos;t have to squint at raw telescope noise! Here is how the live workbench
              keeps everything clear:
            </p>

            <div className="tutorial-cards-3">
              <div className="tutorial-mini-card">
                <div className="tutorial-badge emerald">Feature 1 · Noise Gate</div>
                <h3>Pitch-Black Empty Sky</h3>
                <p>
                  Faint sky ripples are filtered cleanly below ~2.3&sigma; so background space stays
                  dark instead of turning into muddy rainbow blotches.
                </p>
              </div>
              <div className="tutorial-mini-card">
                <div className="tutorial-badge cyan">Feature 2 · Auto Pattern Finder</div>
                <h3>Automatic Candidate List</h3>
                <p>
                  Our detector scans all 6 infrared bands to flag top movers, brightness swings, and
                  4.5 &mu;m heat peaks — click any clue to jump right to it!
                </p>
              </div>
              <div className="tutorial-mini-card">
                <div className="tutorial-badge amber">Feature 3 · Discovery Points</div>
                <h3>Verify &amp; Level Up</h3>
                <p>
                  Confirm whether each flagged clue is a Moving World, Cold World, Flickering Star,
                  or Glitch to earn Citizen Discovery Points and ranks.
                </p>
              </div>
            </div>
          </div>
        )}

        {/* STEP 4: Interactive Practice */}
        {step === 3 && (
          <div className="tutorial-body">
            <p className="tutorial-lead">
              <strong>Try it yourself:</strong> Watch the sky patch below, switch to{" "}
              <strong>Difference Only</strong> if you want a clearer view, and click the{" "}
              <strong>ONE moving object</strong>!
            </p>

            <div className="tutorial-demo-split">
              <div className="tutorial-demo-canvas-wrap">
                <div className="practice-status-bar mono">
                  {practicePhase === "past" && "Showing: PAST (Earlier Scan)"}
                  {practicePhase === "present" && "Showing: PRESENT (Newer Scan)"}
                  {practicePhase === "diff" && "Showing: DIFFERENCE ONLY (Stationary stars erased)"}
                </div>
                <svg viewBox="0 0 100 100" className="tutorial-svg-box practice-grid">
                  <rect width="100" height="100" fill="#050812" rx="6" />
                  {/* Subtle clickable 10x10 pixel grid */}
                  {Array.from({ length: 100 }).map((_, idx) => {
                    const gx = idx % 10;
                    const gy = Math.floor(idx / 10);
                    return (
                      <rect
                        key={idx}
                        x={gx * 10}
                        y={gy * 10}
                        width={10}
                        height={10}
                        fill="transparent"
                        stroke="rgba(148,163,184,0.08)"
                        strokeWidth="0.3"
                        style={{ cursor: "pointer" }}
                        onClick={() => handlePracticeClick(gx, gy)}
                      />
                    );
                  })}

                  {practicePhase !== "diff" &&
                    PRACTICE_STARS.map((s, idx) => (
                      <rect
                        key={idx}
                        x={s.x * 10 + 1}
                        y={s.y * 10 + 1}
                        width={8}
                        height={8}
                        rx={1.5}
                        fill="#fef08a"
                        style={{ pointerEvents: "none" }}
                      />
                    ))}

                  {practicePhase === "past" && (
                    <rect
                      x={PRACTICE_MOVER_PAST.x * 10 + 1}
                      y={PRACTICE_MOVER_PAST.y * 10 + 1}
                      width={8}
                      height={8}
                      rx={1.5}
                      fill="#7dd3fc"
                      style={{ pointerEvents: "none" }}
                    />
                  )}

                  {practicePhase === "present" && (
                    <rect
                      x={PRACTICE_MOVER_PRESENT.x * 10 + 1}
                      y={PRACTICE_MOVER_PRESENT.y * 10 + 1}
                      width={8}
                      height={8}
                      rx={1.5}
                      fill="#fb923c"
                      style={{ pointerEvents: "none" }}
                    />
                  )}

                  {practicePhase === "diff" && (
                    <>
                      <rect
                        x={PRACTICE_MOVER_PAST.x * 10 + 1}
                        y={PRACTICE_MOVER_PAST.y * 10 + 1}
                        width={8}
                        height={8}
                        rx={1.5}
                        fill="#22d3ee"
                        style={{ pointerEvents: "none" }}
                      />
                      <rect
                        x={PRACTICE_MOVER_PRESENT.x * 10 + 1}
                        y={PRACTICE_MOVER_PRESENT.y * 10 + 1}
                        width={8}
                        height={8}
                        rx={1.5}
                        fill="#fb7185"
                        style={{ pointerEvents: "none" }}
                      />
                    </>
                  )}

                  {practiceSolved && (
                    <circle
                      cx={PRACTICE_MOVER_PRESENT.x * 10 + 5}
                      cy={PRACTICE_MOVER_PRESENT.y * 10 + 5}
                      r={7}
                      fill="none"
                      stroke="#34d399"
                      strokeWidth="1.4"
                    />
                  )}
                </svg>

                <div className="tutorial-demo-controls">
                  <button
                    type="button"
                    className={`lens-pill ${practicePhase !== "diff" ? "active" : ""}`}
                    onClick={() => {
                      setBlinkActive(true);
                      setPracticePhase("past");
                    }}
                  >
                    Blink Past &harr; Present
                  </button>
                  <button
                    type="button"
                    className={`lens-pill ${practicePhase === "diff" ? "active" : ""}`}
                    onClick={() => {
                      setBlinkActive(false);
                      setPracticePhase("diff");
                    }}
                  >
                    Difference Only
                  </button>
                </div>
              </div>

              <div className="tutorial-demo-notes">
                {practiceHint ? (
                  <div
                    className={`callout-box ${practiceSolved ? "callout-success" : "callout-warn"}`}
                  >
                    {practiceHint}
                  </div>
                ) : (
                  <div className="callout-box">
                    Click directly on the moving object inside the black square to complete your
                    training!
                  </div>
                )}

                {practiceSolved && (
                  <button
                    type="button"
                    className="btn btn-primary"
                    style={{ width: "100%", padding: "0.7rem", fontSize: "0.95rem" }}
                    onClick={() => completeTutorial(true)}
                  >
                    Enter Live SPHEREx Discovery Workbench (+50 pts) &rarr;
                  </button>
                )}
              </div>
            </div>
          </div>
        )}

        <div className="tutorial-footer">
          <button
            type="button"
            className="btn"
            onClick={() => setStep((s) => Math.max(0, s - 1))}
            disabled={step === 0}
          >
            &larr; Back
          </button>

          <div style={{ display: "flex", gap: "0.55rem" }}>
            {step < 3 ? (
              <button
                type="button"
                className="btn btn-primary"
                onClick={() => setStep((s) => Math.min(3, s + 1))}
              >
                Next Step &rarr;
              </button>
            ) : (
              <button
                type="button"
                className={`btn ${practiceSolved ? "btn-primary" : ""}`}
                onClick={() => completeTutorial(practiceSolved)}
              >
                {practiceSolved ? "Launch Workbench ->" : "Enter Without Bonus ->"}
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
