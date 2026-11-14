import React, { useEffect, useRef, useState } from "react";
import { useAppState } from "../../state/store";

interface AladinGlobal {
  init: Promise<void>;
  aladin: (selectorOrEl: HTMLElement | string, opts: Record<string, unknown>) => unknown;
}

const ALADIN_ESM_URL = "https://cdn.jsdelivr.net/npm/aladin-lite@3/dist/aladin.js";
let aladinApiPromise: Promise<AladinGlobal> | null = null;

function ensureAladinLoaded(): Promise<AladinGlobal> {
  if (!aladinApiPromise) {
    aladinApiPromise = import(/* @vite-ignore */ ALADIN_ESM_URL)
      .then((mod) => {
        const api = (mod?.default ?? mod) as AladinGlobal | undefined;
        if (!api || typeof api.init?.then !== "function") {
          throw new Error("Aladin Lite ES module did not expose init/aladin API.");
        }
        return api;
      })
      .catch((err) => {
        aladinApiPromise = null;
        throw err instanceof Error
          ? err
          : new Error("Aladin Lite CDN script is unreachable or blocked in this environment.");
      });
  }
  return aladinApiPromise;
}

export const AladinInsetModal: React.FC = () => {
  const { aladinOpen, setAladinOpen, manifest } = useAppState();
  const hostRef = useRef<HTMLDivElement | null>(null);
  const [survey, setSurvey] = useState<"P/allWISE/color" | "P/DSS2/color" | "P/2MASS/color">(
    "P/allWISE/color"
  );
  const [aladinErr, setAladinErr] = useState<string | null>(null);

  useEffect(() => {
    if (!aladinOpen || !manifest || !hostRef.current) return;
    let alive = true;
    setAladinErr(null);

    const mount = async () => {
      try {
        const A = await ensureAladinLoaded();
        if (!alive || !hostRef.current) return;
        await A.init;
        if (!alive || !hostRef.current) return;
        hostRef.current.innerHTML = "";
        A.aladin(hostRef.current, {
          survey,
          fov: Math.max(0.12, manifest.grid.fov_deg * 2.5),
          target: `${manifest.grid.ra0.toFixed(6)} ${manifest.grid.dec0.toFixed(6)}`,
          showCooGridControl: true,
          showSimbadPointerControl: true,
        });
      } catch (err) {
        if (alive) {
          setAladinErr(err instanceof Error ? err.message : "Could not initialize Aladin Lite.");
        }
      }
    };

    mount();
    return () => {
      alive = false;
    };
  }, [aladinOpen, manifest, survey]);

  if (!aladinOpen || !manifest) return null;

  return (
    <div
      className="modal-backdrop"
      role="dialog"
      aria-modal="true"
      aria-label="Aladin Sky Survey Context"
      onClick={() => setAladinOpen(false)}
    >
      <div className="modal-card" style={{ maxWidth: "820px" }} onClick={(e) => e.stopPropagation()}>
        <div className="panel-header">
          <div>
            <h2 className="panel-title">Aladin Sky Survey Context</h2>
            <div className="mono" style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
              Target RA {manifest.grid.ra0.toFixed(5)}&deg;, Dec {manifest.grid.dec0.toFixed(5)}&deg;
            </div>
          </div>
          <div style={{ display: "flex", gap: "0.4rem", alignItems: "center" }}>
            <select
              className="select-input"
              style={{ minWidth: "160px", padding: "0.3rem 0.5rem" }}
              value={survey}
              onChange={(e) => setSurvey(e.target.value as typeof survey)}
              aria-label="Background sky survey"
            >
              <option value="P/allWISE/color">AllWISE Mid-IR Color</option>
              <option value="P/2MASS/color">2MASS Near-IR (1998-2001)</option>
              <option value="P/DSS2/color">DSS2 Optical</option>
            </select>
            <button type="button" className="btn btn-ghost" onClick={() => setAladinOpen(false)}>
              Close
            </button>
          </div>
        </div>

        {aladinErr ? (
          <div className="callout-box callout-warn">{aladinErr}</div>
        ) : (
          <div
            ref={hostRef}
            style={{
              width: "100%",
              height: "460px",
              borderRadius: "var(--radius-md)",
              overflow: "hidden",
              border: "1px solid var(--border-strong)",
              background: "#04070f",
            }}
          />
        )}
      </div>
    </div>
  );
};
