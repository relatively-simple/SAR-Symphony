import React, { useEffect, useRef } from "react";
import { renderPlaneToCanvas } from "../../engine/renderer";
import { canvasToSky, skyToFitsPixel } from "../../engine/wcs";
import { useAppState } from "../../state/store";

export const CompareTriptych: React.FC = () => {
  const {
    manifest,
    simpleCompare,
    stretchFn,
    cleanMode,
    crispPixels,
    showFlags,
    selectedCoord,
    pickCoordinate,
    patterns,
    activePatternId,
    canRevealPattern,
    trainingPhase,
    setLens,
    setViewLayout,
  } = useAppState();

  const pastRef = useRef<HTMLCanvasElement | null>(null);
  const presentRef = useRef<HTMLCanvasElement | null>(null);
  const diffRef = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    if (!simpleCompare) return;
    const {
      npix,
      pastPlane,
      presentPlane,
      diffPlane,
      pastFlags,
      presentFlags,
      diffFlags,
    } = simpleCompare;

    if (pastRef.current) {
      renderPlaneToCanvas(pastRef.current, npix, pastPlane, 0, pastFlags, 0, {
        stretchFn,
        lo: 0.5,
        hi: 25,
        diverging: false,
        palette: "inferno",
        showFlags,
        autoRange: true,
        cleanMode,
        crispPixels,
      });
    }
    if (presentRef.current) {
      renderPlaneToCanvas(presentRef.current, npix, presentPlane, 0, presentFlags, 0, {
        stretchFn,
        lo: 0.5,
        hi: 25,
        diverging: false,
        palette: "inferno",
        showFlags,
        autoRange: true,
        cleanMode,
        crispPixels,
      });
    }
    if (diffRef.current) {
      renderPlaneToCanvas(diffRef.current, npix, diffPlane, 0, diffFlags, 0, {
        stretchFn,
        lo: -12,
        hi: 12,
        diverging: true,
        palette: "red-cyan",
        showFlags,
        autoRange: true,
        cleanMode,
        crispPixels,
      });
    }
  }, [simpleCompare, stretchFn, cleanMode, crispPixels, showFlags]);

  if (!manifest || !simpleCompare) {
    return (
      <div
        className="canvas-stage"
        style={{ display: "grid", placeItems: "center", color: "var(--text-muted)" }}
      >
        <span>Building clean multi-band Past vs Present panels...</span>
      </div>
    );
  }

  const npix = manifest.grid.npix;
  const activePattern =
    patterns?.candidates.find((c) => c.id === activePatternId) ?? patterns?.candidates[0] ?? null;

  const toPct = (fx: number, fy: number) => ({
    x: ((fx + 0.5) / npix) * 100,
    y: ((npix - 0.5 - fy) / npix) * 100,
  });

  const targetPt = (() => {
    const [fx, fy] = skyToFitsPixel(manifest.target.ra, manifest.target.dec, manifest.grid);
    if (!Number.isFinite(fx) || !Number.isFinite(fy)) return null;
    return toPct(fx, fy);
  })();

  const clickedPt = (() => {
    if (!selectedCoord) return null;
    const [fx, fy] = skyToFitsPixel(selectedCoord.ra, selectedCoord.dec, manifest.grid);
    if (!Number.isFinite(fx) || !Number.isFinite(fy)) return null;
    return toPct(fx, fy);
  })();

  const handlePanelClick = (
    e: React.MouseEvent<HTMLDivElement>,
    refCanvas: HTMLCanvasElement | null,
    panelKind: "past" | "present" | "diff"
  ) => {
    if (!refCanvas) return;
    const rect = refCanvas.getBoundingClientRect();
    const xPx = ((e.clientX - rect.left) / rect.width) * refCanvas.width;
    const yPx = ((e.clientY - rect.top) / rect.height) * refCanvas.height;
    const res = canvasToSky(xPx, yPx, refCanvas.width, refCanvas.height, manifest.grid);
    pickCoordinate(res.ra, res.dec, res.fitsX, res.fitsY, true, panelKind);
  };

  const renderOverlaySvg = (kind: "past" | "present" | "diff") => (
    <svg className="canvas-overlay-svg" viewBox="0 0 100 100" preserveAspectRatio="none">
      {canRevealPattern &&
        activePattern &&
        Number.isFinite(activePattern.fits_x) &&
        Number.isFinite(activePattern.fits_y) && (() => {
          const nowP = toPct(activePattern.fits_x, activePattern.fits_y);
          const hasOld =
            typeof activePattern.past_fits_x === "number" &&
            typeof activePattern.past_fits_y === "number";
          const oldP = hasOld
            ? toPct(activePattern.past_fits_x!, activePattern.past_fits_y!)
            : null;
          return (
            <g>
              {kind === "past" && oldP && (
                <circle
                  cx={oldP.x}
                  cy={oldP.y}
                  r="4.5"
                  fill="none"
                  stroke="#22d3ee"
                  strokeWidth="0.7"
                />
              )}
              {kind === "present" && (
                <circle
                  cx={nowP.x}
                  cy={nowP.y}
                  r="4.5"
                  fill="none"
                  stroke="#fb7185"
                  strokeWidth="0.7"
                />
              )}
              {kind === "diff" && (
                <>
                  {oldP && (
                    <>
                      <circle
                        cx={oldP.x}
                        cy={oldP.y}
                        r="3.8"
                        fill="none"
                        stroke="#22d3ee"
                        strokeWidth="0.65"
                      />
                      <line
                        x1={oldP.x}
                        y1={oldP.y}
                        x2={nowP.x}
                        y2={nowP.y}
                        stroke="#f8fafc"
                        strokeWidth="0.55"
                        strokeDasharray="1.4 1"
                      />
                    </>
                  )}
                  <circle
                    cx={nowP.x}
                    cy={nowP.y}
                    r="4.2"
                    fill="none"
                    stroke="#fb7185"
                    strokeWidth="0.75"
                  />
                </>
              )}
            </g>
          );
        })()}

      {!canRevealPattern && targetPt && (
        <circle
          cx={targetPt.x}
          cy={targetPt.y}
          r="3.6"
          fill="none"
          stroke="rgba(248, 250, 252, 0.5)"
          strokeWidth="0.45"
          strokeDasharray="1.0 0.8"
        />
      )}

      {clickedPt && (
        <g stroke="#38bdf8" strokeWidth="0.55" fill="none">
          <circle cx={clickedPt.x} cy={clickedPt.y} r="2.6" strokeDasharray="0.9 0.7" />
        </g>
      )}
    </svg>
  );

  const panels: Array<{
    key: "past" | "present" | "diff";
    title: string;
    sub: string;
    ref: React.MutableRefObject<HTMLCanvasElement | null>;
    pillColor: string;
  }> = [
    {
      key: "past",
      title: "1. PAST",
      sub: simpleCompare.pastDate,
      ref: pastRef,
      pillColor: "#38bdf8",
    },
    {
      key: "present",
      title: "2. PRESENT",
      sub: simpleCompare.presentDate,
      ref: presentRef,
      pillColor: "#fbbf24",
    },
    {
      key: "diff",
      title: "3. DIFFERENCE ONLY",
      sub: "Red = Now · Cyan = Before",
      ref: diffRef,
      pillColor: "#fb7185",
    },
  ];

  return (
    <div>
      <div className="compare-triptych">
        {panels.map((p) => (
          <div key={p.key} className="compare-tile">
            <div className="compare-tile-head">
              <span style={{ fontWeight: 700, color: p.pillColor }}>{p.title}</span>
              <span className="mono" style={{ fontSize: "0.7rem", color: "var(--text-muted)" }}>
                {p.sub}
              </span>
            </div>
            <div
              className="canvas-stage"
              style={{ maxHeight: "360px" }}
              onClick={(e) => handlePanelClick(e, p.ref.current, p.key)}
              title="Click any pixel across Past, Present, or Difference to plot its infrared spectrum"
            >
              <canvas ref={p.ref} width={360} height={360} />
              {renderOverlaySvg(p.key)}
            </div>
          </div>
        ))}
      </div>

      <div className="compare-footer-note">
        <span>
          {trainingPhase === "solo" ? (
            "Click any source across Past, Present, or Difference Only to extract its 0.75–5.0 µm spectrum."
          ) : (
            <>
              <strong>How to read:</strong> Stationary stars stay fixed in{" "}
              <strong>1. PAST</strong> and <strong>2. PRESENT</strong>, so they erase to pitch black in{" "}
              <strong>3. DIFFERENCE ONLY</strong>.
            </>
          )}
        </span>
        <div style={{ display: "flex", gap: "0.45rem", flexWrap: "wrap" }}>
          <button
            type="button"
            className="btn"
            style={{ fontSize: "0.75rem", padding: "0.28rem 0.65rem" }}
            onClick={() => setViewLayout("single")}
          >
            Animate Blink &harr;
          </button>
          <button
            type="button"
            className="btn"
            style={{ fontSize: "0.75rem", padding: "0.28rem 0.65rem" }}
            onClick={() => {
              setLens("motion");
              setViewLayout("single");
            }}
          >
            Full-Size Diff
          </button>
        </div>
      </div>
    </div>
  );
};
