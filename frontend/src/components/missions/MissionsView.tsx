import React, { useMemo } from "react";
import { SOLO_PRIMARY_SLUGS, TRAINING_USED_SLUGS } from "../../content/training";
import { useAppState } from "../../state/store";
import { MissionCard } from "./MissionCard";

export const MissionsView: React.FC = () => {
  const { targets, activeMissionSlug, selectMission, trainingPhase } = useAppState();

  const orderedTargets = useMemo(() => {
    const soloFirst = targets.filter((t) =>
      (SOLO_PRIMARY_SLUGS as readonly string[]).includes(t.slug)
    );
    const trainingDoneList = targets.filter((t) =>
      (TRAINING_USED_SLUGS as readonly string[]).includes(t.slug)
    );
    const anyRest = targets.filter(
      (t) =>
        !(SOLO_PRIMARY_SLUGS as readonly string[]).includes(t.slug) &&
        !(TRAINING_USED_SLUGS as readonly string[]).includes(t.slug)
    );
    return [...soloFirst, ...anyRest, ...trainingDoneList];
  }, [targets]);

  // During Training Round 1 & Round 2, keep the workspace clutter-free above the fold with a compact route map
  if (trainingPhase !== "solo") {
    const stepItems = [
      { key: "round1-demo", label: "Round 1 Auto Demo: Barnard's Star" },
      { key: "round2-test1", label: "Round 2 Check 1: WISE 0855" },
      { key: "round2-test2", label: "Round 2 Check 2: RW Aurigae" },
      { key: "solo", label: "Next Solo Targets: Epsilon Indi B & R Draconis" },
    ];
    return (
      <section className="strip-panel" aria-label="Training Progress Map" style={{ padding: "0.55rem 0.9rem" }}>
        <div className="training-route-strip">
          {stepItems.map((it, idx) => {
            const isCurrent = it.key === trainingPhase;
            const currentIdx = stepItems.findIndex((s) => s.key === trainingPhase);
            const isDone = idx < currentIdx;
            return (
              <span
                key={it.key}
                className={`route-pill ${isCurrent ? "current" : isDone ? "done" : "locked"}`}
              >
                {isDone ? "✓ " : isCurrent ? "▶ " : ""}
                {it.label}
              </span>
            );
          })}
        </div>
      </section>
    );
  }

  return (
    <section className="strip-panel" aria-label="Solo SPHEREx Discovery Examples">
      <div className="panel-header" style={{ marginBottom: "0.55rem" }}>
        <div>
          <h1 className="panel-title">
            Remaining Real SPHEREx Examples (Unassisted Mode) + Free Sky Explorer
          </h1>
          <div style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>
            Now explore on your own with no tutorial hints — start with{" "}
            <strong>Epsilon Indi B</strong> &amp; <strong>R Draconis</strong>, revisit any example, or scan custom coordinates in{" "}
            <strong>Free Sky Explorer</strong>.
          </div>
        </div>
      </div>
      <div className="missions-grid">
        {orderedTargets.map((preset) => {
          const isNewSolo = (SOLO_PRIMARY_SLUGS as readonly string[]).includes(preset.slug);
          return (
            <MissionCard
              key={preset.slug}
              preset={preset}
              active={preset.slug === activeMissionSlug}
              roleTag={isNewSolo ? "Solo Target" : "Training Done"}
              onSelect={selectMission}
            />
          );
        })}
      </div>
    </section>
  );
};
