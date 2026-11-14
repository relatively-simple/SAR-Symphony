import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import {
  fetchFramepackBuffer,
  fetchHealth,
  fetchOverlays,
  fetchSession,
  fetchSpectrum,
  fetchTargets,
  fetchTargetSession,
} from "../api/client";
import { startExploreSse } from "../api/sse";
import type {
  FrameMeta,
  HealthStatus,
  LensId,
  OverlaySet,
  ProgressEvent,
  SessionManifest,
  SpectrumResult,
  StretchFn,
  TargetPreset,
} from "../api/types";
import { LENS_SPECS } from "../content/lenses";
import { decodeFramepack, type DecodedFramepack } from "../engine/framepack";
import { useFlipbookPlayback } from "../engine/player";
import { readUrlState, writeUrlState } from "./url";

export type AppMode = "missions" | "explorer";

interface AppContextValue {
  targets: TargetPreset[];
  health: HealthStatus | null;
  mode: AppMode;
  setMode: (m: AppMode) => void;
  activeMissionSlug: string | null;
  activePreset: TargetPreset | null;
  manifest: SessionManifest | null;
  sessionLoading: boolean;
  sessionError: string | null;

  lens: LensId;
  setLens: (l: LensId) => void;
  activePack: DecodedFramepack | null;
  activeFrames: FrameMeta[];
  productLoading: boolean;

  frameIndex: number;
  setFrameIndex: (idx: number) => void;
  stepFrame: (delta: number) => void;
  playing: boolean;
  setPlaying: (p: boolean) => void;
  fps: number;
  setFps: (fps: number) => void;

  proOpen: boolean;
  setProOpen: (v: boolean) => void;
  stretchFn: StretchFn;
  setStretchFn: (s: StretchFn) => void;
  loOverride: number | null;
  hiOverride: number | null;
  setStretchBounds: (lo: number | null, hi: number | null) => void;
  showFlags: boolean;
  setShowFlags: (v: boolean) => void;
  detectorFilter: number | null;
  setDetectorFilter: (d: number | null) => void;

  overlayGaia: boolean;
  setOverlayGaia: (v: boolean) => void;
  overlayWise: boolean;
  setOverlayWise: (v: boolean) => void;
  overlays: OverlaySet | null;
  aladinOpen: boolean;
  setAladinOpen: (v: boolean) => void;
  glossaryOpen: boolean;
  setGlossaryOpen: (v: boolean) => void;

  selectedCoord: { ra: number; dec: number; x?: number; y?: number } | null;
  pickCoordinate: (ra: number, dec: number, x?: number, y?: number) => Promise<void>;
  spectrum: SpectrumResult | null;
  spectrumLoading: boolean;
  spectrumError: string | null;

  exploreProgress: ProgressEvent | null;
  exploring: boolean;
  exploreError: string | null;
  runExplore: (ra: string, dec: string, fov: number, targetLens?: LensId) => void;
  selectMission: (slug: string) => Promise<void>;
}

const AppContext = createContext<AppContextValue | null>(null);

export const AppProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [targets, setTargets] = useState<TargetPreset[]>([]);
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [mode, setModeState] = useState<AppMode>("missions");
  const [activeMissionSlug, setActiveMissionSlug] = useState<string | null>(null);
  const [manifest, setManifest] = useState<SessionManifest | null>(null);
  const [sessionLoading, setSessionLoading] = useState(false);
  const [sessionError, setSessionError] = useState<string | null>(null);

  const [packs, setPacks] = useState<Record<string, DecodedFramepack>>({});
  const [productLoading, setProductLoading] = useState(false);

  const [lens, setLensState] = useState<LensId>("motion");
  const [frameIndex, setFrameIndexState] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [fps, setFps] = useState(2);

  const [proOpen, setProOpen] = useState(false);
  const [stretchFn, setStretchFn] = useState<StretchFn>("asinh");
  const [loOverride, setLoOverride] = useState<number | null>(null);
  const [hiOverride, setHiOverride] = useState<number | null>(null);
  const [showFlags, setShowFlags] = useState(false);
  const [detectorFilter, setDetectorFilter] = useState<number | null>(null);

  const [overlayGaia, setOverlayGaia] = useState(true);
  const [overlayWise, setOverlayWise] = useState(true);
  const [overlays, setOverlays] = useState<OverlaySet | null>(null);
  const [aladinOpen, setAladinOpen] = useState(false);
  const [glossaryOpen, setGlossaryOpen] = useState(false);

  const [selectedCoord, setSelectedCoord] = useState<{
    ra: number;
    dec: number;
    x?: number;
    y?: number;
  } | null>(null);
  const [spectrum, setSpectrum] = useState<SpectrumResult | null>(null);
  const [spectrumLoading, setSpectrumLoading] = useState(false);
  const [spectrumError, setSpectrumError] = useState<string | null>(null);

  const [exploreProgress, setExploreProgress] = useState<ProgressEvent | null>(null);
  const [exploring, setExploring] = useState(false);
  const [exploreError, setExploreError] = useState<string | null>(null);

  const cancelSseRef = useRef<(() => void) | null>(null);
  const packCacheRef = useRef<Record<string, DecodedFramepack>>({});
  const packOrderRef = useRef<string[]>([]);
  const sessionReqRef = useRef(0);
  const spectrumReqRef = useRef(0);

  const activePreset = useMemo(
    () => targets.find((t) => t.slug === activeMissionSlug) ?? null,
    [targets, activeMissionSlug]
  );

  const activeProductKey = LENS_SPECS[lens].productKey;
  const activePack = manifest ? packs[`${manifest.session_id}:${activeProductKey}`] ?? null : null;

  const activeFrames = useMemo(() => {
    if (!manifest) return [];
    const list = manifest.frames[activeProductKey] ?? [];
    if (lens === "visits" && detectorFilter !== null) {
      return list.filter((f) => f.detector === detectorFilter);
    }
    return list;
  }, [manifest, activeProductKey, lens, detectorFilter]);

  const setStretchBounds = useCallback((lo: number | null, hi: number | null) => {
    setLoOverride(lo);
    setHiOverride(hi);
  }, []);

  const pickCoordinate = useCallback(
    async (ra: number, dec: number, x?: number, y?: number) => {
      if (!manifest || !Number.isFinite(ra) || !Number.isFinite(dec)) return;
      const specReq = ++spectrumReqRef.current;
      setSelectedCoord({ ra, dec, x, y });
      setSpectrumLoading(true);
      setSpectrumError(null);
      try {
        const res = await fetchSpectrum(manifest.session_id, ra, dec);
        if (specReq !== spectrumReqRef.current) return;
        setSpectrum(res);
      } catch (err) {
        if (specReq !== spectrumReqRef.current) return;
        setSpectrumError(err instanceof Error ? err.message : "Failed extracting spectrum.");
      } finally {
        if (specReq === spectrumReqRef.current) {
          setSpectrumLoading(false);
        }
      }
    },
    [manifest]
  );

  const ensureProductLoaded = useCallback(
    async (sess: SessionManifest, productKey: string) => {
      const cacheKey = `${sess.session_id}:${productKey}`;
      const existing = packCacheRef.current[cacheKey];
      if (existing) {
        setPacks((prev) => (prev[cacheKey] === existing ? prev : { ...prev, [cacheKey]: existing }));
        return;
      }
      const pInfo = sess.products[productKey];
      if (!pInfo) return;
      setProductLoading(true);
      try {
        const buf = await fetchFramepackBuffer(pInfo.url);
        const decoded = decodeFramepack(buf);
        packCacheRef.current[cacheKey] = decoded;
        packOrderRef.current = [...packOrderRef.current.filter((k) => k !== cacheKey), cacheKey];
        let evictedKeys: string[] = [];
        while (packOrderRef.current.length > 12) {
          const oldest = packOrderRef.current.shift();
          if (oldest && !oldest.startsWith(`${sess.session_id}:`)) {
            delete packCacheRef.current[oldest];
            evictedKeys.push(oldest);
          } else if (oldest) {
            packOrderRef.current.push(oldest);
            break;
          }
        }
        setPacks((prev) => {
          const next = { ...prev, [cacheKey]: decoded };
          for (const k of evictedKeys) delete next[k];
          return next;
        });
      } catch (err) {
        setSessionError(err instanceof Error ? err.message : "Could not decode image stack.");
      } finally {
        setProductLoading(false);
      }
    },
    []
  );

  const applySessionManifest = useCallback(
    async (sess: SessionManifest, desiredLens: LensId, slug: string | null, reqId: number) => {
      if (reqId !== sessionReqRef.current) return;
      const specReq = ++spectrumReqRef.current;

      setManifest(sess);
      setOverlays(null);
      setFrameIndexState(0);
      setPlaying(false);
      setLoOverride(null);
      setHiOverride(null);
      setDetectorFilter(null);
      setSessionError(null);

      // Ensure chosen lens has an existing product; otherwise fall back cleanly
      const chosenProduct = LENS_SPECS[desiredLens].productKey;
      const effectiveLens: LensId = sess.products[chosenProduct]
        ? desiredLens
        : sess.products.pass_coadds
        ? "variable"
        : "visits";
      setLensState(effectiveLens);

      const mjdRef =
        sess.target.mjd_ref ??
        (sess.passes.length > 0 ? sess.passes[Math.floor(sess.passes.length / 2)].mjd_mid : 60900);

      const npix = sess.grid.npix;
      setSelectedCoord({
        ra: sess.target.ra,
        dec: sess.target.dec,
        x: Math.floor(npix / 2),
        y: Math.floor(npix / 2),
      });
      setSpectrumLoading(true);
      setSpectrumError(null);

      // Load primary framepack, overlays, and initial center spectrum concurrently
      const overlaysPromise = fetchOverlays(sess.grid.ra0, sess.grid.dec0, sess.grid.fov_deg, mjdRef, slug)
        .then((ov) => {
          if (reqId === sessionReqRef.current) setOverlays(ov);
        })
        .catch(() => {
          if (reqId === sessionReqRef.current) setOverlays(null);
        });

      const spectrumPromise = fetchSpectrum(sess.session_id, sess.target.ra, sess.target.dec)
        .then((res) => {
          if (specReq === spectrumReqRef.current) setSpectrum(res);
        })
        .catch((err) => {
          if (specReq === spectrumReqRef.current) {
            setSpectrumError(err instanceof Error ? err.message : "Spectrum extraction failed.");
          }
        })
        .finally(() => {
          if (specReq === spectrumReqRef.current) setSpectrumLoading(false);
        });

      await Promise.all([
        ensureProductLoaded(sess, LENS_SPECS[effectiveLens].productKey),
        overlaysPromise,
        spectrumPromise,
      ]);
    },
    [ensureProductLoaded]
  );

  const selectMission = useCallback(
    async (slug: string) => {
      cancelSseRef.current?.();
      const reqId = ++sessionReqRef.current;
      setExploring(false);
      setExploreError(null);
      setModeState("missions");
      setActiveMissionSlug(slug);
      setSessionLoading(true);
      setSessionError(null);
      try {
        const presetMeta = targets.find((t) => t.slug === slug);
        const sess = await fetchTargetSession(slug);
        if (reqId !== sessionReqRef.current) return;
        const defaultLens = presetMeta?.default_lens ?? "motion";
        await applySessionManifest(sess, defaultLens, slug, reqId);
        if (reqId === sessionReqRef.current) {
          writeUrlState({ mode: "missions", mission: slug, lens: defaultLens });
        }
      } catch (err) {
        if (reqId === sessionReqRef.current) {
          setSessionError(err instanceof Error ? err.message : "Could not load mission data.");
        }
      } finally {
        if (reqId === sessionReqRef.current) {
          setSessionLoading(false);
        }
      }
    },
    [applySessionManifest, targets]
  );

  const runExplore = useCallback(
    (ra: string, dec: string, fov: number, targetLens: LensId = "motion") => {
      cancelSseRef.current?.();
      const reqId = ++sessionReqRef.current;
      setModeState("explorer");
      setActiveMissionSlug(null);
      setExploring(true);
      setExploreError(null);
      setSessionError(null);
      setExploreProgress({
        stage: "resolve",
        message: "Resolving sky coordinates...",
        done: 0,
        total: 1,
      });

      writeUrlState({ mode: "explorer", ra, dec, fov, lens: targetLens });

      const cancel = startExploreSse(ra, dec, fov, null, {
        onProgress: (ev) => {
          if (reqId === sessionReqRef.current) setExploreProgress(ev);
        },
        onDone: async (sessionId) => {
          if (reqId !== sessionReqRef.current) return;
          setExploring(false);
          setSessionLoading(true);
          try {
            const sess = await fetchSession(sessionId);
            if (reqId !== sessionReqRef.current) return;
            await applySessionManifest(sess, targetLens, null, reqId);
          } catch (err) {
            if (reqId === sessionReqRef.current) {
              setSessionError(err instanceof Error ? err.message : "Failed loading session.");
            }
          } finally {
            if (reqId === sessionReqRef.current) {
              setSessionLoading(false);
            }
          }
        },
        onError: (message) => {
          if (reqId !== sessionReqRef.current) return;
          setExploring(false);
          setExploreError(message);
        },
      });
      cancelSseRef.current = cancel;
    },
    [applySessionManifest]
  );

  const setMode = useCallback((nextMode: AppMode) => {
    setModeState(nextMode);
    if (nextMode === "explorer") {
      writeUrlState({
        mode: "explorer",
        ra: manifest ? manifest.grid.ra0.toFixed(6) : undefined,
        dec: manifest ? manifest.grid.dec0.toFixed(6) : undefined,
        fov: manifest ? manifest.grid.fov_deg : undefined,
        lens,
      });
    } else if (activeMissionSlug) {
      writeUrlState({ mode: "missions", mission: activeMissionSlug, lens });
    }
  }, [activeMissionSlug, lens, manifest]);

  const setLens = useCallback(
    (nextLens: LensId) => {
      setLensState(nextLens);
      setFrameIndexState(0);
      setLoOverride(null);
      setHiOverride(null);
      setPlaying(false);
      if (manifest) {
        ensureProductLoaded(manifest, LENS_SPECS[nextLens].productKey);
      }
      if (mode === "explorer" && manifest) {
        writeUrlState({
          mode: "explorer",
          ra: manifest.grid.ra0.toFixed(6),
          dec: manifest.grid.dec0.toFixed(6),
          fov: manifest.grid.fov_deg,
          lens: nextLens,
        });
      } else if (activeMissionSlug) {
        writeUrlState({ mode: "missions", mission: activeMissionSlug, lens: nextLens });
      }
    },
    [activeMissionSlug, ensureProductLoaded, manifest, mode]
  );

  const setFrameIndex = useCallback(
    (idx: number) => {
      if (activeFrames.length === 0) return;
      const wrapped = ((idx % activeFrames.length) + activeFrames.length) % activeFrames.length;
      setFrameIndexState(wrapped);
    },
    [activeFrames.length]
  );

  const stepFrame = useCallback(
    (delta: number) => {
      setFrameIndexState((prev) => {
        if (activeFrames.length === 0) return 0;
        return (((prev + delta) % activeFrames.length) + activeFrames.length) % activeFrames.length;
      });
    },
    [activeFrames.length]
  );

  useFlipbookPlayback(playing, fps, activeFrames.length, () => {
    stepFrame(1);
  });

  // Initial app boot
  useEffect(() => {
    let alive = true;
    const init = async () => {
      try {
        const [presetList, healthRes] = await Promise.all([
          fetchTargets(),
          fetchHealth().catch(() => null),
        ]);
        if (!alive) return;
        setTargets(presetList);
        if (healthRes) setHealth(healthRes);

        const url = readUrlState();
        if (url.mode === "explorer" && url.ra && url.dec) {
          runExplore(url.ra, url.dec, url.fov ?? 0.05, url.lens ?? "motion");
          return;
        }

        const chosenSlug =
          url.mission && presetList.some((p) => p.slug === url.mission)
            ? url.mission
            : presetList.find((p) => p.has_preset_bundle)?.slug ?? presetList[0]?.slug;

        if (chosenSlug) {
          const presetMeta = presetList.find((p) => p.slug === chosenSlug);
          const reqId = ++sessionReqRef.current;
          setModeState("missions");
          setActiveMissionSlug(chosenSlug);
          setSessionLoading(true);
          try {
            const sess = await fetchTargetSession(chosenSlug);
            if (!alive || reqId !== sessionReqRef.current) return;
            await applySessionManifest(
              sess,
              url.lens ?? presetMeta?.default_lens ?? "motion",
              chosenSlug,
              reqId
            );
          } catch (err) {
            if (alive && reqId === sessionReqRef.current) {
              setSessionError(err instanceof Error ? err.message : "Failed initializing target.");
            }
          } finally {
            if (alive && reqId === sessionReqRef.current) setSessionLoading(false);
          }
        }
      } catch (err) {
        if (alive) {
          setSessionError(err instanceof Error ? err.message : "Cannot reach SPHEREx backend.");
        }
      }
    };
    init();
    return () => {
      alive = false;
      cancelSseRef.current?.();
    };
  }, [applySessionManifest, runExplore]);

  const value = useMemo<AppContextValue>(
    () => ({
      targets,
      health,
      mode,
      setMode,
      activeMissionSlug,
      activePreset,
      manifest,
      sessionLoading,
      sessionError,
      lens,
      setLens,
      activePack,
      activeFrames,
      productLoading,
      frameIndex,
      setFrameIndex,
      stepFrame,
      playing,
      setPlaying,
      fps,
      setFps,
      proOpen,
      setProOpen,
      stretchFn,
      setStretchFn,
      loOverride,
      hiOverride,
      setStretchBounds,
      showFlags,
      setShowFlags,
      detectorFilter,
      setDetectorFilter,
      overlayGaia,
      setOverlayGaia,
      overlayWise,
      setOverlayWise,
      overlays,
      aladinOpen,
      setAladinOpen,
      glossaryOpen,
      setGlossaryOpen,
      selectedCoord,
      pickCoordinate,
      spectrum,
      spectrumLoading,
      spectrumError,
      exploreProgress,
      exploring,
      exploreError,
      runExplore,
      selectMission,
    }),
    [
      targets,
      health,
      mode,
      setMode,
      activeMissionSlug,
      activePreset,
      manifest,
      sessionLoading,
      sessionError,
      lens,
      setLens,
      activePack,
      activeFrames,
      productLoading,
      frameIndex,
      setFrameIndex,
      stepFrame,
      playing,
      fps,
      proOpen,
      stretchFn,
      loOverride,
      hiOverride,
      setStretchBounds,
      showFlags,
      detectorFilter,
      overlayGaia,
      overlayWise,
      overlays,
      aladinOpen,
      glossaryOpen,
      selectedCoord,
      pickCoordinate,
      spectrum,
      spectrumLoading,
      spectrumError,
      exploreProgress,
      exploring,
      exploreError,
      runExplore,
      selectMission,
    ]
  );

  return React.createElement(AppContext.Provider, { value }, children);
};

export function useAppState(): AppContextValue {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error("useAppState must be used inside AppProvider");
  return ctx;
}
