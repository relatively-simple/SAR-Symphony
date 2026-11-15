import React, { useEffect, useState } from "react";
import { useAppState } from "../../state/store";

export const PlaybackBar: React.FC = () => {
  const {
    lens,
    viewLayout,
    setViewLayout,
    activeFrames,
    frameIndex,
    setFrameIndex,
    stepFrame,
    playing,
    setPlaying,
    fps,
    setFps,
  } = useAppState();
  const [copied, setCopied] = useState(false);

  const inCompareMode = lens === "blink" && viewLayout === "compare";
  const total = activeFrames.length;
  const current = activeFrames[frameIndex];

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement | null)?.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || tag === "BUTTON" || tag === "A") {
        return;
      }
      if (e.code === "Space" && total > 1) {
        e.preventDefault();
        setPlaying(!playing);
      } else if (e.code === "ArrowLeft" && total > 1) {
        e.preventDefault();
        stepFrame(-1);
      } else if (e.code === "ArrowRight" && total > 1) {
        e.preventDefault();
        stepFrame(1);
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [playing, setPlaying, stepFrame, total]);

  const copyShareUrl = async () => {
    try {
      await navigator.clipboard.writeText(window.location.href);
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    } catch {
      // clipboard blocked in sandbox
    }
  };

  if (inCompareMode) {
    return (
      <div className="playback-bar" style={{ justifyContent: "space-between" }}>
        <span style={{ fontSize: "0.78rem", color: "var(--text-secondary)" }}>
          Showing synchronized <strong>Past</strong>, <strong>Present</strong>, and{" "}
          <strong>Difference Only</strong> panels side-by-side.
        </span>
        <div style={{ display: "flex", gap: "0.45rem", alignItems: "center" }}>
          <button
            type="button"
            className="btn btn-primary"
            style={{ fontSize: "0.75rem", padding: "0.3rem 0.65rem" }}
            onClick={() => {
              setViewLayout("single");
              setPlaying(true);
            }}
          >
            Play Blink Loop
          </button>
          <button
            type="button"
            className="btn btn-ghost"
            style={{ fontSize: "0.73rem", padding: "0.26rem 0.55rem" }}
            onClick={copyShareUrl}
          >
            {copied ? "Copied Link" : "Share Link"}
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="playback-bar">
      <button
        type="button"
        className="btn"
        onClick={() => stepFrame(-1)}
        disabled={total <= 1}
        aria-label="Previous frame"
        title="Previous frame (Left Arrow)"
      >
        Prev
      </button>

      <button
        type="button"
        className="btn btn-primary"
        onClick={() => setPlaying(!playing)}
        disabled={total <= 1}
        title="Toggle flipbook animation (Spacebar)"
      >
        {playing ? "Pause" : "Play Flipbook"}
      </button>

      <button
        type="button"
        className="btn"
        onClick={() => stepFrame(1)}
        disabled={total <= 1}
        aria-label="Next frame"
        title="Next frame (Right Arrow)"
      >
        Next
      </button>

      <input
        className="frame-scrubber"
        type="range"
        min={0}
        max={Math.max(0, total - 1)}
        value={frameIndex}
        onChange={(e) => {
          setPlaying(false);
          setFrameIndex(Number(e.target.value));
        }}
        disabled={total <= 1}
        aria-label="Flipbook frame scrubber"
      />

      <div className="control-row" style={{ gap: "0.35rem" }}>
        <span style={{ color: "var(--text-muted)" }}>Speed</span>
        {[1, 2, 4, 8].map((val) => (
          <button
            key={val}
            type="button"
            className={`detector-chip ${fps === val ? "active" : ""}`}
            onClick={() => setFps(val)}
          >
            {val} fps
          </button>
        ))}
      </div>

      {current && (
        <span className="mono" style={{ fontSize: "0.74rem", color: "var(--text-muted)" }}>
          MJD {current.mjd.toFixed(1)}
        </span>
      )}

      <button
        type="button"
        className="btn btn-ghost"
        style={{ fontSize: "0.73rem", padding: "0.26rem 0.55rem" }}
        onClick={copyShareUrl}
        title="Copy deep-link URL to this sky target and lens"
      >
        {copied ? "Copied Link" : "Share Link"}
      </button>
    </div>
  );
};
