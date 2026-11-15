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
  fetchAiExplain,
  fetchEonet,
  fetchFramepackBuffer,
  fetchHealth,
  fetchLiveStory,
  fetchOverlays,
  fetchPatterns,
  fetchSpectrum,
  fetchTargets,
  fetchTargetSession,
  type LiveStoryParams,
} from "../api/client";
import type {
  AiExplainResponse,
  EonetEvent,
  HealthStatus,
  LensId,
  OverlaySet,
  PatternCandidate,
  PatternReport,
  ProgressEvent,
  SessionManifest,
  SignalId,
  SpectrumResult,
  TargetPreset,
} from "../api/types";
import { decodeFramepack, type DecodedFramepack } from "../engine/framepack";
import { readUrlState, writeUrlState } from "./url";

export type AppMode = "missions" | "explorer";

const VALID_SIGNALS = new Set<SignalId>(["radar", "rain", "wind", "temp", "optical", "nightlights"]);

export interface AppContextValue {
  targets: TargetPreset[];
  health: HealthStatus | null;
  mode: AppMode;
  setMode: (mode: AppMode) => void;
  activeMissionSlug: string | null;
  activePreset: TargetPreset | null;
  manifest: SessionManifest | null;
  packs: Record<string, DecodedFramepack>;
  sessionLoading: boolean;
  sessionError: string | null;

  lens: LensId;
  setLens: (lens: LensId) => void;
  productLoading: boolean;

  frameIndex: number;
  setFrameIndex: (idx: number) => void;
  storyPlaying: boolean;
  setStoryPlaying: (p: boolean) => void;

  overlays: OverlaySet | null;
  glossaryOpen: boolean;
  setGlossaryOpen: (v: boolean) => void;

  patterns: PatternReport | null;
  patternsLoading: boolean;
  activePatternId: string | null;
  selectPattern: (cand: PatternCandidate) => Promise<void>;

  selectedCoord: { ra: number; dec: number; x?: number; y?: number } | null;
  pickCoordinate: (
    lon: number,
    lat: number,
    x?: number,
    y?: number,
    isUserClick?: boolean
  ) => Promise<void>;
  spectrum: SpectrumResult | null;
  spectrumLoading: boolean;
  spectrumError: string | null;

  aiExplanation: AiExplainResponse | null;
  aiLoading: boolean;
  askAiDirector: (question?: string) => Promise<void>;

  exploreProgress: ProgressEvent | null;
  exploring: boolean;
  exploreError: string | null;
  runLiveStorySearch: (params: LiveStoryParams) => Promise<void>;
  runExplore: (lon: string, lat: string, fov: number) => void;
  selectMission: (slug: string) => Promise<void>;

  activeLayers: SignalId[];
  setActiveLayers: (layers: SignalId[]) => void;
  toggleLayer: (layer: SignalId) => void;
  illusionGuard: boolean;
  setIllusionGuard: (on: boolean) => void;
  activeSceneIndex: number;
  selectStoryScene: (index: number) => void;

  guidedTourActive: boolean;
  guidedTourStep: number;
  startGuidedTour: () => void;
  stopGuidedTour: () => void;
  nextTourStep: () => void;
  prevTourStep: () => void;

  eonetEvents: EonetEvent[];
  eonetLoading: boolean;
  eonetError: string | null;
  loadEonetEvents: (category?: string) => Promise<void>;
}

const AppContext = createContext<AppContextValue | null>(null);

export const AppProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const initialUrl = useMemo(() => readUrlState(), []);

  const [targets, setTargets] = useState<TargetPreset[]>([]);
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [mode, setModeState] = useState<AppMode>("missions");
  const [activeMissionSlug, setActiveMissionSlug] = useState<string | null>(null);
  const [manifest, setManifest] = useState<SessionManifest | null>(null);
  const [sessionLoading, setSessionLoading] = useState(false);
  const [sessionError, setSessionError] = useState<string | null>(null);

  const [packs, setPacks] = useState<Record<string, DecodedFramepack>>({});
  const [productLoading, setProductLoading] = useState(false);

  const [lens, setLensState] = useState<LensId>("radar");
  const [frameIndex, setFrameIndexState] = useState(0);
  const [storyPlaying, setStoryPlaying] = useState(false);

  const [overlays, setOverlays] = useState<OverlaySet | null>(null);
  const [glossaryOpen, setGlossaryOpen] = useState(false);

  const [patterns, setPatterns] = useState<PatternReport | null>(null);
  const [patternsLoading, setPatternsLoading] = useState(false);
  const [activePatternId, setActivePatternId] = useState<string | null>(null);

  const [selectedCoord, setSelectedCoord] = useState<{
    ra: number;
    dec: number;
    x?: number;
    y?: number;
  } | null>(null);
  const [spectrum, setSpectrum] = useState<SpectrumResult | null>(null);
  const [spectrumLoading, setSpectrumLoading] = useState(false);
  const [spectrumError, setSpectrumError] = useState<string | null>(null);

  const [aiExplanation, setAiExplanation] = useState<AiExplainResponse | null>(null);
  const [aiLoading, setAiLoading] = useState(false);

  const [exploreProgress, setExploreProgress] = useState<ProgressEvent | null>(null);
  const [exploring, setExploring] = useState(false);
  const [exploreError, setExploreError] = useState<string | null>(null);

  const [activeLayers, setActiveLayers] = useState<SignalId[]>(["temp", "wind"]);
  const [illusionGuard, setIllusionGuard] = useState<boolean>(true);
  const [activeSceneIndex, setActiveSceneIndex] = useState<number>(0);
  const [guidedTourActive, setGuidedTourActive] = useState<boolean>(false);
  const [guidedTourStep, setGuidedTourStep] = useState<number>(0);

  const [eonetEvents, setEonetEvents] = useState<EonetEvent[]>([]);
  const [eonetLoading, setEonetLoading] = useState<boolean>(false);
  const [eonetError, setEonetError] = useState<string | null>(null);

  const packCacheRef = useRef<Record<string, DecodedFramepack>>({});
  const packOrderRef = useRef<string[]>([]);
  const sessionReqRef = useRef(0);
  const spectrumReqRef = useRef(0);
  const aiReqRef = useRef(0);

  const activePreset = useMemo(
    () => targets.find((t) => t.slug === activeMissionSlug) ?? null,
    [targets, activeMissionSlug]
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
        const evictedKeys: string[] = [];
        while (packOrderRef.current.length > 24) {
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
        setSessionError(err instanceof Error ? err.message : "Could not decode multi-sensor cube.");
      } finally {
        setProductLoading(false);
      }
    },
    []
  );

  // Lazy-load any dataset active in activeLayers so Leaflet overlays always have all 6 NASA cubes ready
  useEffect(() => {
    if (!manifest) return;
    for (const sig of activeLayers) {
      void ensureProductLoaded(manifest, sig);
    }
  }, [manifest, activeLayers, ensureProductLoaded]);

  const runAiExplainInternal = useCallback(
    async (
      sess: SessionManifest,
      sceneIdx: number,
      guardOn: boolean,
      coord: { ra: number; dec: number } | null,
      question?: string
    ) => {
      const aiId = ++aiReqRef.current;
      setAiLoading(true);
      try {
        const res = await fetchAiExplain({
          session_id: sess.session_id,
          question: question || "Why did these 6 Earth datasets change in sequence across scenes?",
          scene_index: sceneIdx,
          lat: coord?.dec ?? sess.target.lat ?? sess.target.dec,
          lon: coord?.ra ?? sess.target.lon ?? sess.target.ra,
          illusion_guard: guardOn,
        });
        if (aiId === aiReqRef.current) {
          setAiExplanation(res);
        }
      } catch {
        // leave prior explanation cleanly if aborted
      } finally {
        if (aiId === aiReqRef.current) {
          setAiLoading(false);
        }
      }
    },
    []
  );

  const askAiDirector = useCallback(
    async (question?: string) => {
      if (!manifest) return;
      await runAiExplainInternal(manifest, activeSceneIndex, illusionGuard, selectedCoord, question);
    },
    [activeSceneIndex, illusionGuard, manifest, runAiExplainInternal, selectedCoord]
  );

  const pickCoordinate = useCallback(
    async (lon: number, lat: number, x?: number, y?: number) => {
      if (!manifest || !Number.isFinite(lon) || !Number.isFinite(lat)) return;
      const specReq = ++spectrumReqRef.current;
      const nextCoord = { ra: lon, dec: lat, x, y };
      setSelectedCoord(nextCoord);
      setSpectrumLoading(true);
      setSpectrumError(null);
      try {
        const res = await fetchSpectrum(manifest.session_id, lon, lat);
        if (specReq !== spectrumReqRef.current) return;
        setSpectrum(res);
        void runAiExplainInternal(manifest, activeSceneIndex, illusionGuard, nextCoord);
      } catch (err) {
        if (specReq !== spectrumReqRef.current) return;
        setSpectrumError(err instanceof Error ? err.message : "Failed extracting multi-sensor timeline.");
      } finally {
        if (specReq === spectrumReqRef.current) {
          setSpectrumLoading(false);
        }
      }
    },
    [activeSceneIndex, illusionGuard, manifest, runAiExplainInternal]
  );

  const applySessionManifest = useCallback(
    async (
      sess: SessionManifest,
      desiredLens: LensId,
      slug: string | null,
      reqId: number
    ) => {
      if (reqId !== sessionReqRef.current) return;
      const specReq = ++spectrumReqRef.current;

      setManifest(sess);
      const firstScene = sess.story_scenes?.[0];
      setActiveSceneIndex(0);
      setFrameIndexState(firstScene ? firstScene.frame_index : 0);
      setActiveLayers(
        firstScene?.active_layers && firstScene.active_layers.length > 0
          ? firstScene.active_layers
          : ["temp", "wind", "radar"]
      );
      setStoryPlaying(false);
      setOverlays(null);
      setPatterns(null);
      setActivePatternId(null);
      setPatternsLoading(true);
      setSessionError(null);

      let effectiveLens: LensId = desiredLens;
      if (effectiveLens !== "blink") {
        const prodKey = VALID_SIGNALS.has(effectiveLens as SignalId) ? effectiveLens : "radar";
        if (!sess.products[prodKey]) {
          effectiveLens = sess.products.radar ? "radar" : "pass_coadds" in sess.products ? "blink" : "visits";
        }
      }
      setLensState(effectiveLens);

      const lonVal = sess.target.lon ?? sess.target.ra;
      const latVal = sess.target.lat ?? sess.target.dec;
      const npix = sess.grid.npix;
      const initCoord = {
        ra: lonVal,
        dec: latVal,
        x: Math.floor(npix / 2),
        y: Math.floor(npix / 2),
      };
      setSelectedCoord(initCoord);
      setSpectrumLoading(true);
      setSpectrumError(null);

      const mjdRef =
        sess.target.mjd_ref ??
        (sess.passes.length > 0 ? sess.passes[Math.floor(sess.passes.length / 2)].mjd_mid : 60900);

      const overlaysPromise = fetchOverlays(lonVal, latVal, sess.grid.fov_deg, mjdRef, slug)
        .then((ov) => {
          if (reqId === sessionReqRef.current) setOverlays(ov);
        })
        .catch(() => {
          if (reqId === sessionReqRef.current) setOverlays(null);
        });

      const patternsPromise = fetchPatterns(sess.session_id)
        .then((rep) => {
          if (reqId !== sessionReqRef.current) return;
          setPatterns(rep);
          if (rep.candidates.length > 0) setActivePatternId(rep.candidates[0].id);
        })
        .catch(() => {
          if (reqId === sessionReqRef.current) setPatterns(null);
        })
        .finally(() => {
          if (reqId === sessionReqRef.current) setPatternsLoading(false);
        });

      const spectrumPromise = fetchSpectrum(sess.session_id, lonVal, latVal)
        .then((res) => {
          if (specReq === spectrumReqRef.current) setSpectrum(res);
        })
        .catch((err) => {
          if (specReq === spectrumReqRef.current) {
            setSpectrumError(err instanceof Error ? err.message : "Timeline extraction failed.");
          }
        })
        .finally(() => {
          if (specReq === spectrumReqRef.current) setSpectrumLoading(false);
        });

      const aiPromise = runAiExplainInternal(sess, 0, illusionGuard, initCoord);

      const preloadKeys = Array.from(
        new Set([
          "radar",
          "rain",
          "wind",
          "temp",
          "optical",
          "nightlights",
          ...(firstScene?.active_layers ?? []),
        ])
      ).filter((k) => Boolean(sess.products[k]));

      await Promise.all([
        ...preloadKeys.map((k) => ensureProductLoaded(sess, k)),
        overlaysPromise,
        patternsPromise,
        spectrumPromise,
        aiPromise,
      ]);
    },
    [ensureProductLoaded, illusionGuard, runAiExplainInternal]
  );

  const selectMission = useCallback(
    async (slug: string) => {
      const reqId = ++sessionReqRef.current;
      setExploring(false);
      setExploreError(null);
      setModeState("missions");
      setActiveMissionSlug(slug);
      setSessionLoading(true);
      setSessionError(null);
      try {
        const sess = await fetchTargetSession(slug);
        if (reqId !== sessionReqRef.current) return;
        await applySessionManifest(sess, "radar", slug, reqId);
        if (reqId === sessionReqRef.current) {
          writeUrlState({ mode: "missions", mission: slug, lens: "radar", scene: 0 });
        }
      } catch (err) {
        if (reqId === sessionReqRef.current) {
          setSessionError(err instanceof Error ? err.message : "Could not load event data.");
        }
      } finally {
        if (reqId === sessionReqRef.current) {
          setSessionLoading(false);
        }
      }
    },
    [applySessionManifest]
  );

  const runLiveStorySearch = useCallback(
    async (params: LiveStoryParams) => {
      const reqId = ++sessionReqRef.current;
      setModeState("explorer");
      setExploring(true);
      setExploreError(null);
      setSessionError(null);
      setExploreProgress({
        stage: "fetch",
        message: `Resolving NASA/historical Earth signals for "${params.title || params.q || "event"}"...`,
        done: 1,
        total: 2,
      });

      try {
        const sess = await fetchLiveStory(params);
        if (reqId !== sessionReqRef.current) return;
        const matchedPresetSlug = sess.source === "preset" ? sess.session_id : null;
        setActiveMissionSlug(matchedPresetSlug);
        setExploring(false);
        setSessionLoading(true);
        await applySessionManifest(sess, "radar", matchedPresetSlug, reqId);
        if (reqId === sessionReqRef.current) {
          setExploreProgress(null);
          if (matchedPresetSlug) {
            setModeState("missions");
            writeUrlState({ mode: "missions", mission: matchedPresetSlug, lens: "radar", scene: 0 });
          } else {
            writeUrlState({
              mode: "explorer",
              ra: String(sess.target.lon ?? sess.target.ra),
              dec: String(sess.target.lat ?? sess.target.dec),
              fov: sess.grid.fov_deg,
              lens: "radar",
            });
          }
        }
      } catch (err) {
        if (reqId === sessionReqRef.current) {
          setExploring(false);
          const msg = err instanceof Error ? err.message : "Could not resolve that event or place.";
          setExploreError(msg);
          setSessionError(msg);
        }
      } finally {
        if (reqId === sessionReqRef.current) {
          setSessionLoading(false);
        }
      }
    },
    [applySessionManifest]
  );

  const runExplore = useCallback(
    (lonStr: string, latStr: string, fov: number) => {
      const lonNum = Number(lonStr);
      const latNum = Number(latStr);
      if (Number.isFinite(lonNum) && Number.isFinite(latNum)) {
        void runLiveStorySearch({ lat: latNum, lon: lonNum, fov });
      } else {
        void runLiveStorySearch({ q: `${latStr} ${lonStr}`.trim(), fov });
      }
    },
    [runLiveStorySearch]
  );

  const setMode = useCallback(
    (nextMode: AppMode) => {
      setModeState(nextMode);
    },
    []
  );

  const setLens = useCallback((nextLens: LensId) => {
    setLensState(nextLens);
  }, []);

  const selectPattern = useCallback(
    async (cand: PatternCandidate) => {
      setActivePatternId(cand.id);
      await pickCoordinate(cand.ra, cand.dec, cand.fits_x, cand.fits_y);
    },
    [pickCoordinate]
  );

  const setFrameIndex = useCallback(
    (idx: number) => {
      const total = manifest?.passes.length || 12;
      const wrapped = ((idx % total) + total) % total;
      setFrameIndexState(wrapped);
    },
    [manifest?.passes.length]
  );

  const selectStoryScene = useCallback(
    (index: number) => {
      const scenes = manifest?.story_scenes;
      if (!scenes || scenes.length === 0) return;
      const safeIdx = Math.max(0, Math.min(scenes.length - 1, index));
      setActiveSceneIndex(safeIdx);
      const sc = scenes[safeIdx];
      setFrameIndexState(sc.frame_index);
      if (sc.active_layers && sc.active_layers.length > 0) {
        setActiveLayers(sc.active_layers);
        const primarySig = sc.active_layers[0] as SignalId;
        if (primarySig && VALID_SIGNALS.has(primarySig)) {
          setLensState(primarySig);
        }
      }
      if (manifest) {
        void runAiExplainInternal(manifest, safeIdx, illusionGuard, selectedCoord);
      }
    },
    [illusionGuard, manifest, runAiExplainInternal, selectedCoord]
  );

  // Auto-play 5 Domino Story scenes when user clicks Play Domino Story
  useEffect(() => {
    if (!storyPlaying || !manifest?.story_scenes?.length) return;
    const totalScenes = manifest.story_scenes.length;
    const timer = window.setInterval(() => {
      setActiveSceneIndex((prev) => {
        const next = (prev + 1) % totalScenes;
        const sc = manifest.story_scenes?.[next];
        if (sc) {
          setFrameIndexState(sc.frame_index);
          if (sc.active_layers?.length) {
            setActiveLayers(sc.active_layers);
            const primarySig = sc.active_layers[0] as SignalId;
            if (primarySig && VALID_SIGNALS.has(primarySig)) setLensState(primarySig);
          }
          void runAiExplainInternal(manifest, next, illusionGuard, selectedCoord);
        }
        if (next === 0) {
          setStoryPlaying(false);
        }
        return next;
      });
    }, 4200);
    return () => window.clearInterval(timer);
  }, [illusionGuard, manifest, runAiExplainInternal, selectedCoord, storyPlaying]);

  const toggleLayer = useCallback((layer: SignalId) => {
    setActiveLayers((prev) => {
      if (prev.includes(layer)) {
        if (prev.length <= 1) return prev;
        return prev.filter((l) => l !== layer);
      }
      return [...prev, layer];
    });
  }, []);

  const startGuidedTour = useCallback(() => {
    setGuidedTourActive(true);
    setGuidedTourStep(0);
  }, []);

  const stopGuidedTour = useCallback(() => {
    setGuidedTourActive(false);
  }, []);

  const nextTourStep = useCallback(() => {
    setGuidedTourStep((s) => Math.min(s + 1, 4));
  }, []);

  const prevTourStep = useCallback(() => {
    setGuidedTourStep((s) => Math.max(s - 1, 0));
  }, []);

  const loadEonetEvents = useCallback(async (cat?: string) => {
    setEonetLoading(true);
    setEonetError(null);
    try {
      const list = await fetchEonet(cat);
      setEonetEvents(list);
    } catch (err) {
      setEonetError(err instanceof Error ? err.message : "Failed loading NASA EONET feed");
    } finally {
      setEonetLoading(false);
    }
  }, []);

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
          await runLiveStorySearch({ lat: Number(url.dec), lon: Number(url.ra), fov: url.fov ?? 0.5 });
          return;
        }

        const startSlug =
          url.mission && presetList.some((p) => p.slug === url.mission)
            ? url.mission
            : presetList.find((p) => p.slug === "kandy-floods")?.slug ?? presetList[0]?.slug;

        if (startSlug) {
          const reqId = ++sessionReqRef.current;
          setModeState("missions");
          setActiveMissionSlug(startSlug);
          setSessionLoading(true);
          try {
            const sess = await fetchTargetSession(startSlug);
            if (!alive || reqId !== sessionReqRef.current) return;
            await applySessionManifest(sess, "radar", startSlug, reqId);
          } catch (err) {
            if (alive && reqId === sessionReqRef.current) {
              setSessionError(err instanceof Error ? err.message : "Failed initializing Earth event.");
            }
          } finally {
            if (alive && reqId === sessionReqRef.current) setSessionLoading(false);
          }
        }
      } catch (err) {
        if (alive) {
          setSessionError(err instanceof Error ? err.message : "Cannot reach SAR Symphony backend.");
        }
      }
    };
    init();
    return () => {
      alive = false;
    };
    // Run once on initial mount
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const value = useMemo<AppContextValue>(
    () => ({
      targets,
      health,
      mode,
      setMode,
      activeMissionSlug,
      activePreset,
      manifest,
      packs,
      sessionLoading,
      sessionError,
      lens,
      setLens,
      productLoading,
      frameIndex,
      setFrameIndex,
      storyPlaying,
      setStoryPlaying,
      overlays,
      glossaryOpen,
      setGlossaryOpen,
      patterns,
      patternsLoading,
      activePatternId,
      selectPattern,
      selectedCoord,
      pickCoordinate,
      spectrum,
      spectrumLoading,
      spectrumError,
      aiExplanation,
      aiLoading,
      askAiDirector,
      exploreProgress,
      exploring,
      exploreError,
      runLiveStorySearch,
      runExplore,
      selectMission,
      activeLayers,
      setActiveLayers,
      toggleLayer,
      illusionGuard,
      setIllusionGuard,
      activeSceneIndex,
      selectStoryScene,
      guidedTourActive,
      guidedTourStep,
      startGuidedTour,
      stopGuidedTour,
      nextTourStep,
      prevTourStep,
      eonetEvents,
      eonetLoading,
      eonetError,
      loadEonetEvents,
    }),
    [
      targets,
      health,
      mode,
      setMode,
      activeMissionSlug,
      activePreset,
      manifest,
      packs,
      sessionLoading,
      sessionError,
      lens,
      setLens,
      productLoading,
      frameIndex,
      setFrameIndex,
      storyPlaying,
      overlays,
      glossaryOpen,
      patterns,
      patternsLoading,
      activePatternId,
      selectPattern,
      selectedCoord,
      pickCoordinate,
      spectrum,
      spectrumLoading,
      spectrumError,
      aiExplanation,
      aiLoading,
      askAiDirector,
      exploreProgress,
      exploring,
      exploreError,
      runLiveStorySearch,
      runExplore,
      selectMission,
      activeLayers,
      toggleLayer,
      illusionGuard,
      activeSceneIndex,
      selectStoryScene,
      guidedTourActive,
      guidedTourStep,
      startGuidedTour,
      stopGuidedTour,
      nextTourStep,
      prevTourStep,
      eonetEvents,
      eonetLoading,
      eonetError,
      loadEonetEvents,
    ]
  );

  return React.createElement(AppContext.Provider, { value }, children);
};

export function useAppState(): AppContextValue {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error("useAppState must be used inside AppProvider");
  return ctx;
}
