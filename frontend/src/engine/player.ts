import { useEffect, useRef } from "react";

/**
 * Smooth frame-flipbook timer driven by requestAnimationFrame.
 * Advances frameIndex at `fps` frames per second while `playing` is true.
 */
export function useFlipbookPlayback(
  playing: boolean,
  fps: number,
  frameCount: number,
  onAdvance: () => void
): void {
  const cbRef = useRef(onAdvance);
  cbRef.current = onAdvance;

  useEffect(() => {
    if (!playing || frameCount <= 1) return;

    let rafId = 0;
    let lastTick = performance.now();
    const intervalMs = 1000 / Math.max(0.5, fps);

    const step = (now: number) => {
      if (now - lastTick >= intervalMs) {
        lastTick = now - ((now - lastTick) % intervalMs);
        cbRef.current();
      }
      rafId = requestAnimationFrame(step);
    };

    rafId = requestAnimationFrame(step);
    return () => cancelAnimationFrame(rafId);
  }, [playing, fps, frameCount]);
}
