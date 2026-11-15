import React from "react";
import { GlossaryModal } from "./components/layout/GlossaryModal";
import { TopNav } from "./components/layout/TopNav";
import { PatternFinderCard } from "./components/side/PatternFinderCard";
import { SpectrumChart } from "./components/side/SpectrumChart";
import { TrainingDirectorBar } from "./components/tutorial/TrainingDirectorBar";
import { StoryDirectorBar } from "./components/viewer/StoryDirectorBar";
import { StoryMapCanvas } from "./components/viewer/StoryMapCanvas";
import { AppProvider, useAppState } from "./state/store";

const StudioWorkspace: React.FC = () => {
  const { sessionError } = useAppState();

  return (
    <div className="studio-shell">
      <TopNav />
      <TrainingDirectorBar />

      {sessionError && (
        <div className="studio-error-banner" role="alert">
          {sessionError}
        </div>
      )}

      <main className="studio-main">
        {/* Left Stage: Interactive Multi-Scale Leaflet Story Map + Bottom 5-Step Domino Dock */}
        <section className="studio-left-column" aria-label="Interactive Story Map and Domino Sequence">
          <StoryMapCanvas />
          <StoryDirectorBar />
        </section>

        {/* Right Panel: AI Causal Domino Breakdown & Equal-Scale 6 NASA Dataset Timeline */}
        <aside className="studio-right-column" aria-label="AI Causal Breakdown and Signal Timeline">
          <PatternFinderCard />
          <SpectrumChart />
        </aside>
      </main>

      <GlossaryModal />
    </div>
  );
};

export function App() {
  return (
    <AppProvider>
      <StudioWorkspace />
    </AppProvider>
  );
}

export default App;
