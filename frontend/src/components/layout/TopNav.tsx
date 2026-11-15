import React, { useEffect, useState } from "react";
import type { EonetEvent } from "../../api/types";
import { useAppState } from "../../state/store";

const FEATURED_QUERIES = [
  { label: "Kandy Floods (2024)", kind: "preset", slug: "kandy-floods", query: "Kandy flood" },
  { label: "Dubai Flash Floods (2024)", kind: "search", query: "Dubai flood 2024" },
  { label: "Valencia DANA Flood (2024)", kind: "search", query: "Valencia flood" },
  { label: "Maui Wildfire (2023)", kind: "preset", slug: "maui-wildfire", query: "Maui wildfire" },
  { label: "Amazon Drought (2024)", kind: "preset", slug: "amazon-drought-fire", query: "Amazon drought" },
  { label: "Mahaweli Rice Cycle (2025)", kind: "preset", slug: "mahaweli-rice", query: "Mahaweli rice" },
  { label: "Jakobshavn Glacier (2024)", kind: "preset", slug: "jakobshavn-glacier", query: "Jakobshavn glacier" },
  { label: "Pakistan Mega-Floods (2022)", kind: "search", query: "Pakistan flood 2022" },
];

export const TopNav: React.FC = () => {
  const {
    activeMissionSlug,
    manifest,
    selectMission,
    runLiveStorySearch,
    setGlossaryOpen,
    startGuidedTour,
    eonetEvents,
    eonetLoading,
    eonetError,
    loadEonetEvents,
    exploring,
  } = useAppState();

  const [searchText, setSearchText] = useState("");
  const [searchOpen, setSearchOpen] = useState(false);
  const [eonetOpen, setEonetOpen] = useState(false);

  useEffect(() => {
    if (eonetOpen && eonetEvents.length === 0 && !eonetLoading) {
      void loadEonetEvents();
    }
  }, [eonetOpen, eonetEvents.length, eonetLoading, loadEonetEvents]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const q = searchText.trim();
    if (!q) return;
    setSearchOpen(false);
    void runLiveStorySearch({ q });
  };

  const handlePickFeatured = (item: (typeof FEATURED_QUERIES)[number]) => {
    setSearchOpen(false);
    setEonetOpen(false);
    setSearchText(item.label);
    if (item.kind === "preset" && item.slug) {
      void selectMission(item.slug);
    } else {
      void runLiveStorySearch({ q: item.query });
    }
  };

  const handlePickEonet = (ev: EonetEvent) => {
    const [lon, lat] = ev.coordinates;
    setEonetOpen(false);
    setSearchOpen(false);
    setSearchText(ev.title);
    void runLiveStorySearch({
      lat,
      lon,
      title: ev.title,
      category: ev.category,
    });
  };

  return (
    <header className="topbar-studio">
      {/* Left: Brand Identity */}
      <div className="brand-compact">
        <div className="brand-mark-studio" aria-hidden="true">
          🛰️
        </div>
        <div>
          <div className="brand-title-studio">SAR Symphony</div>
          <div className="brand-sub-studio">
            Visualizing Earth&apos;s Cause-and-Effect Chains
          </div>
        </div>
      </div>

      {/* Center: Actual Event & Cause Search + Flagship Quick Chips + Live NASA EONET */}
      <div className="command-search-wrap">
        <form className="event-search-form" onSubmit={handleSubmit}>
          <input
            type="text"
            value={searchText}
            onFocus={() => setSearchOpen(true)}
            onChange={(e) => setSearchText(e.target.value)}
            placeholder="Search disaster or city (e.g. Kandy flood, Dubai 2024, Valencia)..."
            aria-label="Search disaster event or location"
          />
          <button type="submit" className="btn btn-coral btn-xs" disabled={exploring}>
            {exploring ? "Scanning..." : "Explore Cause"}
          </button>
          <button
            type="button"
            className={`btn btn-ghost btn-xs ${searchOpen ? "active-pop" : ""}`}
            onClick={() => {
              setSearchOpen((v) => !v);
              setEonetOpen(false);
            }}
          >
            Events ▾
          </button>
          <button
            type="button"
            className={`btn btn-ghost btn-xs ${eonetOpen ? "active-pop" : ""}`}
            onClick={() => {
              setEonetOpen((v) => !v);
              setSearchOpen(false);
            }}
          >
            🌍 Live EONET
          </button>
        </form>

        {/* Events Catalog Popover */}
        {searchOpen && (
          <div className="command-popover" role="region" aria-label="Curated and historical events">
            <div className="popover-head">
              <strong>Curated Benchmark &amp; Historical Disaster Causes</strong>
              <button type="button" className="btn btn-ghost btn-xs" onClick={() => setSearchOpen(false)}>
                ✕
              </button>
            </div>
            <div className="popover-grid">
              {FEATURED_QUERIES.map((item) => {
                const isActive =
                  (item.slug && activeMissionSlug === item.slug) ||
                  manifest?.target.name?.toLowerCase().includes(item.label.split(" ")[0].toLowerCase());
                return (
                  <button
                    key={item.label}
                    type="button"
                    className={`popover-item ${isActive ? "active" : ""}`}
                    onClick={() => handlePickFeatured(item)}
                  >
                    <span>{item.label}</span>
                    <span className="mono">{item.kind === "preset" ? "Curated" : "Archive"}</span>
                  </button>
                );
              })}
            </div>
          </div>
        )}

        {/* Live NASA EONET Active Disasters Popover */}
        {eonetOpen && (
          <div className="command-popover" role="region" aria-label="Live NASA EONET events">
            <div className="popover-head">
              <strong>🌍 NASA EONET v3 Active Natural Disasters</strong>
              <button type="button" className="btn btn-ghost btn-xs" onClick={() => setEonetOpen(false)}>
                ✕
              </button>
            </div>
            {eonetLoading ? (
              <div className="popover-status">Fetching live NASA EONET events...</div>
            ) : eonetError ? (
              <div className="popover-status error">{eonetError}</div>
            ) : (
              <div className="popover-list">
                {eonetEvents.slice(0, 10).map((ev) => (
                  <button
                    key={ev.id}
                    type="button"
                    className="popover-eonet-row"
                    onClick={() => handlePickEonet(ev)}
                  >
                    <div>
                      <div className="ev-title">{ev.title}</div>
                      <div className="ev-meta mono">
                        {ev.category} · {ev.date.slice(0, 10)} · ({ev.coordinates[1].toFixed(2)}°, {ev.coordinates[0].toFixed(2)}°)
                      </div>
                    </div>
                    <span className="ev-go">Trace ➜</span>
                  </button>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Right: Guided Tour & Science Guide */}
      <div className="nav-actions-studio">
        <button
          type="button"
          className="btn btn-amber btn-xs"
          onClick={startGuidedTour}
          title="Open 60-second visual walkthrough"
        >
          ✨ 60s Tour
        </button>

        <button
          type="button"
          className="btn btn-teal btn-xs"
          onClick={() => setGlossaryOpen(true)}
        >
          📖 SAR Guide
        </button>

        <span
          className="si-watermark-tag"
          title="SI-assisted code, UI & Earth signal synthesis (no audio generated; open Earth data, no NASA branding)"
        >
          SI-gen
        </span>
      </div>
    </header>
  );
};
