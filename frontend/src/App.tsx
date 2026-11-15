import React from "react";
import { Spinner } from "./components/common/Spinner";
import { ExplorerView } from "./components/explorer/ExplorerView";
import { CitationsBar } from "./components/layout/CitationsBar";
import { GlossaryModal } from "./components/layout/GlossaryModal";
import { TopNav } from "./components/layout/TopNav";
import { MissionsView } from "./components/missions/MissionsView";
import { ProDrawer } from "./components/pro/ProDrawer";
import { AladinInsetModal } from "./components/side/AladinInsetModal";
import { MissionBriefingCard } from "./components/side/MissionBriefingCard";
import { OverlayControlsCard } from "./components/side/OverlayControlsCard";
import { PatternFinderCard } from "./components/side/PatternFinderCard";
import { SpectrumChart } from "./components/side/SpectrumChart";
import { TrainingDirectorBar } from "./components/tutorial/TrainingDirectorBar";
import { CompareTriptych } from "./components/viewer/CompareTriptych";
import { FlipbookCanvas } from "./components/viewer/FlipbookCanvas";
import { LensBar } from "./components/viewer/LensBar";
import { PlaybackBar } from "./components/viewer/PlaybackBar";
import { AppProvider, useAppState } from "./state/store";

const Workbench: React.FC = () => {
  const {
    mode,
    lens,
    viewLayout,
    sessionLoading,
    productLoading,
    sessionError,
    manifest,
  } = useAppState();

  return (
    <>
      <TopNav />
      <main className="app-shell">
        <TrainingDirectorBar />
        {mode === "missions" ? <MissionsView /> : <ExplorerView />}

        {sessionError && (
          <div className="callout-box callout-warn" role="alert">
            <strong>Notice:</strong> {sessionError}
          </div>
        )}

        <div className="workbench">
          {/* Left: Interactive Past vs Present / Flipbook Canvas & Controls */}
          <section className="panel-card" aria-label="SPHEREx Discovery Flipbook Viewer">
            <div className="panel-header" style={{ marginBottom: "0.55rem" }}>
              <h2 className="panel-title">Interactive SPHEREx Discovery Viewer</h2>
              {(sessionLoading || productLoading) && (
                <Spinner label="Loading calibrated float32 tiles..." />
              )}
            </div>

            <LensBar />

            <div style={{ marginTop: "0.7rem" }}>
              {!manifest ? (
                <div
                  className="canvas-stage"
                  style={{ display: "grid", placeItems: "center", color: "var(--text-muted)" }}
                >
                  {sessionLoading ? (
                    <Spinner label="Preparing discovery stack..." />
                  ) : (
                    <span>Select a sky patch or scan coordinates to begin.</span>
                  )}
                </div>
              ) : lens === "blink" && viewLayout === "compare" ? (
                <CompareTriptych />
              ) : (
                <FlipbookCanvas />
              )}
            </div>

            <PlaybackBar />
            <ProDrawer />
          </section>

          {/* Right: Classification Verdict, Spectrum, Reference & Overlays */}
          <aside className="side-stack" aria-label="Discovery Context and Spectrum">
            <PatternFinderCard />
            <SpectrumChart />
            <MissionBriefingCard />
            <OverlayControlsCard />
          </aside>
        </div>

        <CitationsBar />
      </main>

      <GlossaryModal />
      <AladinInsetModal />
    </>
  );
};

export const App: React.FC = () => (
  <AppProvider>
    <Workbench />
  </AppProvider>
);

export default App;
