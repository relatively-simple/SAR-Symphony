import React, { useEffect, useMemo, useRef } from "react";
import { LENS_SPECS } from "../../content/lenses";
import { renderFrameToCanvas } from "../../engine/renderer";
import { canvasToSky, skyToFitsPixel } from "../../engine/wcs";
import { useAppState } from "../../state/store";

function propagateGaiaClient(
  ra2016: number,
  dec2016: number,
  pmra: number | null | undefined,
  pmdec: number | null | undefined,
  mjdTarget: number
): [number, number] {
  if (!pmra && !pmdec) return [ra2016, dec2016];
  const mjdYear = 2000.0 + (mjdTarget - 51544.5) / 365.25;
  const dt = mjdYear - 2016.0;
  const cosd = Math.max(Math.cos((dec2016 * Math.PI) / 180), 0.05);
  const dra = ((pmra ?? 0) / 1000.0) * dt / 3600.0 / cosd;
  const ddec = ((pmdec ?? 0) / 1000.0) * dt / 3600.0;
  return [(ra2016 + dra + 360) % 360, Math.max(-90, Math.min(90, dec2016 + ddec))];
}

export const FlipbookCanvas: React.FC = () => {
  const {
    manifest,
    activePack,
    activeFrames,
    frameIndex,
    lens,
    stretchFn,
    loOverride,
    hiOverride,
    showFlags,
    cleanMode,
    crispPixels,
    patterns,
    activePatternId,
    canRevealPattern,
    overlays,
    overlayGaia,
    overlayWise,
    selectedCoord,
    pickCoordinate,
  } = useAppState();

  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const activeMeta = activeFrames[frameIndex] ?? null;
  const spec = LENS_SPECS[lens];

  // Resolve real pack index matching activeFrames[frameIndex] (important when detector filter shrinks activeFrames)
  const packFrameIdx = useMemo(() => {
    if (!activePack || !activeMeta) return 0;
    const idx = activePack.frameIds.indexOf(activeMeta.id);
    return idx >= 0 ? idx : Math.min(frameIndex, activePack.nFrames - 1);
  }, [activePack, activeMeta, frameIndex]);

  const lo = loOverride ?? activeMeta?.stretch_hint.p_lo ?? (spec.diverging ? -1.0 : 0.0);
  const hi = hiOverride ?? activeMeta?.stretch_hint.p_hi ?? 1.0;

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !activePack) return;
    renderFrameToCanvas(canvas, activePack, packFrameIdx, {
      stretchFn,
      lo,
      hi,
      diverging: spec.diverging,
      palette: spec.palette,
      showFlags,
      autoRange: loOverride === null && hiOverride === null,
      cleanMode,
      crispPixels,
    });
  }, [
    activePack,
    packFrameIdx,
    stretchFn,
    lo,
    hi,
    loOverride,
    hiOverride,
    spec.diverging,
    spec.palette,
    showFlags,
    cleanMode,
    crispPixels,
  ]);

  const handleClick = (e: React.MouseEvent<HTMLDivElement>) => {
    const canvas = canvasRef.current;
    if (!canvas || !manifest) return;
    const rect = canvas.getBoundingClientRect();
    const xPx = ((e.clientX - rect.left) / rect.width) * canvas.width;
    const yPx = ((e.clientY - rect.top) / rect.height) * canvas.height;
    const res = canvasToSky(xPx, yPx, canvas.width, canvas.height, manifest.grid);
    pickCoordinate(res.ra, res.dec, res.fitsX, res.fitsY, true);
  };

  const npix = manifest?.grid.npix ?? 1;
  const targetMarker = useMemo(() => {
    if (!manifest) return null;
    const [fx, fy] = skyToFitsPixel(manifest.target.ra, manifest.target.dec, manifest.grid);
    if (!Number.isFinite(fx) || !Number.isFinite(fy)) return null;
    return { pctX: ((fx + 0.5) / npix) * 100, pctY: ((npix - 0.5 - fy) / npix) * 100 };
  }, [manifest, npix]);

  const clickedMarker = useMemo(() => {
    if (!manifest || !selectedCoord) return null;
    const [fx, fy] = skyToFitsPixel(selectedCoord.ra, selectedCoord.dec, manifest.grid);
    if (!Number.isFinite(fx) || !Number.isFinite(fy)) return null;
    return { pctX: ((fx + 0.5) / npix) * 100, pctY: ((npix - 0.5 - fy) / npix) * 100 };
  }, [manifest, selectedCoord, npix]);

  const patternOverlay = useMemo(() => {
    const cand =
      patterns?.candidates.find((c) => c.id === activePatternId) ?? patterns?.candidates[0] ?? null;
    if (!cand || !Number.isFinite(cand.fits_x) || !Number.isFinite(cand.fits_y)) return null;
    const nowX = ((cand.fits_x + 0.5) / npix) * 100;
    const nowY = ((npix - 0.5 - cand.fits_y) / npix) * 100;
    const hasPast =
      typeof cand.past_fits_x === "number" &&
      typeof cand.past_fits_y === "number" &&
      Number.isFinite(cand.past_fits_x) &&
      Number.isFinite(cand.past_fits_y);
    return {
      nowX,
      nowY,
      pastX: hasPast ? ((cand.past_fits_x! + 0.5) / npix) * 100 : null,
      pastY: hasPast ? ((npix - 0.5 - cand.past_fits_y!) / npix) * 100 : null,
    };
  }, [patterns, activePatternId, npix]);

  const currentMjd = activeMeta?.mjd ?? overlays?.mjd_ref ?? 61000;

  const colorbarStyle = useMemo(() => {
    if (lens === "motion") {
      return { background: "linear-gradient(90deg, #22d3ee 0%, #0f172a 50%, #fb7185 100%)" };
    }
    if (lens === "coldglow") {
      return { background: "linear-gradient(90deg, #0b0e18 0%, #c2410c 55%, #fde047 100%)" };
    }
    if (lens === "rgb") {
      return { background: "linear-gradient(90deg, #3b82f6 0%, #22c55e 50%, #ef4444 100%)" };
    }
    return { background: "linear-gradient(90deg, #0b0e18 0%, #9f2d68 55%, #fde047 100%)" };
  }, [lens]);

  return (
    <div>
      <div className="canvas-stage" onClick={handleClick} title="Click anywhere on sky to extract 0.75-5.0 um SPHEREx spectrum">
        <canvas ref={canvasRef} width={512} height={512} />

        {/* Vector overlays: Target reticle, clicked pixel cursor, Gaia DR3 & AllWISE */}
        <svg className="canvas-overlay-svg" viewBox="0 0 100 100" preserveAspectRatio="none">
          {/* North-Up East-Left compass */}
          <g stroke="rgba(226,232,240,0.65)" strokeWidth="0.35" fill="rgba(226,232,240,0.8)">
            <line x1="92" y1="92" x2="92" y2="84" />
            <line x1="92" y1="92" x2="84" y2="92" />
            <text x="91.2" y="82.5" fontSize="2.7" stroke="none">N</text>
            <text x="80.5" y="92.8" fontSize="2.7" stroke="none">E</text>
          </g>

          {overlayWise &&
            overlays?.allwise.map((w, idx) => {
              if (!manifest) return null;
              const [fx, fy] = skyToFitsPixel(w.ra, w.dec, manifest.grid);
              const x = ((fx + 0.5) / npix) * 100;
              const y = ((npix - 0.5 - fy) / npix) * 100;
              if (!Number.isFinite(x) || !Number.isFinite(y) || x < 0 || x > 100 || y < 0 || y > 100) {
                return null;
              }
              return (
                <circle
                  key={`w_${idx}`}
                  cx={x}
                  cy={y}
                  r="1.35"
                  fill="none"
                  stroke="#fbbf24"
                  strokeWidth="0.32"
                  strokeOpacity="0.85"
                />
              );
            })}

          {overlayGaia &&
            overlays?.gaia.map((g, idx) => {
              if (!manifest) return null;
              const [raMjd, decMjd] = propagateGaiaClient(g.ra, g.dec, g.pmra, g.pmdec, currentMjd);
              const [fx, fy] = skyToFitsPixel(raMjd, decMjd, manifest.grid);
              const x = ((fx + 0.5) / npix) * 100;
              const y = ((npix - 0.5 - fy) / npix) * 100;
              if (!Number.isFinite(x) || !Number.isFinite(y) || x < 0 || x > 100 || y < 0 || y > 100) {
                return null;
              }
              return (
                <g key={`g_${idx}`} stroke="#34d399" strokeWidth="0.32" strokeOpacity="0.85">
                  <line x1={x - 1.1} y1={y} x2={x + 1.1} y2={y} />
                  <line x1={x} y1={y - 1.1} x2={x} y2={y + 1.1} />
                </g>
              );
            })}

          {canRevealPattern && patternOverlay && (
            <g fill="none">
              {patternOverlay.pastX !== null && patternOverlay.pastY !== null && (
                <>
                  <circle
                    cx={patternOverlay.pastX}
                    cy={patternOverlay.pastY}
                    r="2.9"
                    stroke="#22d3ee"
                    strokeWidth="0.4"
                  />
                  <line
                    x1={patternOverlay.pastX}
                    y1={patternOverlay.pastY}
                    x2={patternOverlay.nowX}
                    y2={patternOverlay.nowY}
                    stroke="#f8fafc"
                    strokeWidth="0.38"
                    strokeDasharray="1.1 0.8"
                  />
                </>
              )}
              <circle
                cx={patternOverlay.nowX}
                cy={patternOverlay.nowY}
                r="3.8"
                stroke="#fb923c"
                strokeWidth="0.45"
                strokeDasharray="1.3 0.7"
              />
            </g>
          )}

          {targetMarker && (
            <g stroke="rgba(248, 250, 252, 0.55)" strokeWidth="0.3" fill="none">
              <circle cx={targetMarker.pctX} cy={targetMarker.pctY} r="3.2" strokeDasharray="0.9 0.7" />
            </g>
          )}

          {clickedMarker && (
            <g stroke="#38bdf8" strokeWidth="0.45" fill="none">
              <circle cx={clickedMarker.pctX} cy={clickedMarker.pctY} r="2.1" />
              <circle cx={clickedMarker.pctX} cy={clickedMarker.pctY} r="0.35" fill="#38bdf8" />
            </g>
          )}
        </svg>

        {activeMeta && (
          <>
            <div className="hud-badge hud-top-left mono">
              {activeMeta.pass_label} &middot; {activeMeta.date_utc.split(" ")[0]}
              {activeMeta.detector ? ` · D${activeMeta.detector}` : ""}
              {activeMeta.wavelength_um ? ` · ${activeMeta.wavelength_um.toFixed(2)} um` : ""}
            </div>
            <div className="hud-badge hud-top-right mono">
              Frame {frameIndex + 1}/{activeFrames.length}
            </div>
            {manifest && (
              <div className="hud-badge hud-bottom-left mono">
                FOV {manifest.grid.fov_deg.toFixed(2)}&deg; ({npix}px @ {manifest.grid.pixscale_arcsec}&quot;/px)
              </div>
            )}
          </>
        )}
      </div>

      <div className="colorbar-wrap">
        <div className="colorbar-bar" style={colorbarStyle} />
        <div className="colorbar-labels">
          <span>{spec.legendLeft}</span>
          <span>Click image anywhere to inspect 0.75&ndash;5.0 &mu;m spectrum</span>
          <span>{spec.legendRight}</span>
        </div>
      </div>
    </div>
  );
};
