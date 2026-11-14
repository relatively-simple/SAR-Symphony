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
import { SpectrumChart } from "./components/side/SpectrumChart";
import { FlipbookCanvas } from "./components/viewer/FlipbookCanvas";
import { LensBar } from "./components/viewer/LensBar";
import { PlaybackBar } from "./components/viewer/PlaybackBar";
import { AppProvider, useAppState } from "./state/store";

const Workbench: React.FC = () => {
  const { mode, sessionLoading, productLoading, sessionError, manifest } = useAppState();

  return (
    <>
      <TopNav />
      <main className="app-shell">
        {mode === "missions" ? <MissionsView /> : <ExplorerView />}

        {sessionError && (
          <div className="callout-box callout-warn" role="alert">
            <strong>Notice:</strong> {sessionError}
          </div>
        )}

        <div className="workbench">
          {/* Left: Interactive Flipbook Canvas & Controls */}
          <section className="panel-card" aria-label="SPHEREx Discovery Flipbook Viewer">
            <div className="panel-header" style={{ marginBottom: "0.55rem" }}>
              <h2 className="panel-title">Interactive SPHEREx Flipbook</h2>
              {(sessionLoading || productLoading) && (
                <Spinner label="Loading calibrated float32 tiles..." />
              )}
            </div>

            <LensBar />

            <div style={{ marginTop: "0.7rem" }}>
              {manifest ? (
                <FlipbookCanvas />
              ) : (
                <div
                  className="canvas-stage"
                  style={{ display: "grid", placeItems: "center", color: "var(--text-muted)" }}
                >
                  {sessionLoading ? (
                    <Spinner label="Preparing discovery stack..." />
                  ) : (
                    <span>Select a mission or scan sky coordinates to begin.</span>
                  )}
                </div>
              )}
            </div>

            <PlaybackBar />
            <ProDrawer />
          </section>

          {/* Right: Briefing, Click-to-Spectrum & Multi-Mission Overlays */}
          <aside className="side-stack" aria-label="Discovery Context and Spectrum">
            <MissionBriefingCard />
            <SpectrumChart />
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
