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
  fetchPatterns,
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
  PatternCandidate,
  PatternReport,
  ProgressEvent,
  SessionManifest,
  SpectrumResult,
  StretchFn,
  TargetPreset,
  ViewLayout,
} from "../api/types";
import { LENS_SPECS } from "../content/lenses";
import { decodeFramepack, type DecodedFramepack } from "../engine/framepack";
import { useFlipbookPlayback } from "../engine/player";
import { buildSimpleCompare, type SimpleCompareData } from "../engine/simpleCompare";
import { readUrlState, writeUrlState } from "./url";

export type AppMode = "missions" | "explorer";

export interface SavedVerdict {
  choice: string;
  matched: boolean;
  points: number;
}

const TUTORIAL_STORAGE_KEY = "kkn_tutorial_v1";
const PROGRESS_STORAGE_KEY = "kkn_progress_v1";

function loadSavedProgress(): { points: number; verdicts: Record<string, SavedVerdict> } {
  try {
    const raw = localStorage.getItem(PROGRESS_STORAGE_KEY);
    if (!raw) return { points: 0, verdicts: {} };
    const parsed = JSON.parse(raw);
    return {
      points: typeof parsed.points === "number" ? parsed.points : 0,
      verdicts: parsed.verdicts && typeof parsed.verdicts === "object" ? parsed.verdicts : {},
    };
  } catch {
    return { points: 0, verdicts: {} };
  }
}

function loadTutorialDone(): boolean {
  try {
    return localStorage.getItem(TUTORIAL_STORAGE_KEY) === "done";
  } catch {
    return false;
  }
}

export function getHunterRank(points: number): string {
  if (points >= 200) return "Planet X Pioneer";
  if (points >= 110) return "Pattern Analyst";
  if (points >= 50) return "Sky Spotter";
  return "Curious Explorer";
}

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
  viewLayout: ViewLayout;
  setViewLayout: (v: ViewLayout) => void;
  simpleCompare: SimpleCompareData | null;
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
  cleanMode: boolean;
  setCleanMode: (v: boolean) => void;
  crispPixels: boolean;
  setCrispPixels: (v: boolean) => void;
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

  tutorialDone: boolean;
  tutorialOpen: boolean;
  setTutorialOpen: (v: boolean) => void;
  completeTutorial: (awardBonus?: boolean) => void;

  discoveryPoints: number;
  hunterRank: string;
  verdicts: Record<string, SavedVerdict>;
  patterns: PatternReport | null;
  patternsLoading: boolean;
  activePatternId: string | null;
  selectPattern: (cand: PatternCandidate) => Promise<void>;
  submitVerdict: (cand: PatternCandidate, choice: string) => SavedVerdict;

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
  const initialProgress = useMemo(() => loadSavedProgress(), []);
  const initialTutorialDone = useMemo(() => loadTutorialDone(), []);
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

  const [lens, setLensState] = useState<LensId>("blink");
  const [viewLayout, setViewLayout] = useState<ViewLayout>("compare");
  const [frameIndex, setFrameIndexState] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [fps, setFps] = useState(2);

  const [proOpen, setProOpen] = useState(false);
  const [stretchFn, setStretchFn] = useState<StretchFn>("asinh");
  const [loOverride, setLoOverride] = useState<number | null>(null);
  const [hiOverride, setHiOverride] = useState<number | null>(null);
  const [showFlags, setShowFlags] = useState(false);
  const [cleanMode, setCleanMode] = useState(true);
  const [crispPixels, setCrispPixels] = useState(true);
  const [detectorFilter, setDetectorFilter] = useState<number | null>(null);

  // Decluttered by default: let citizen scientists toggle Gaia/AllWISE clutter on when desired
  const [overlayGaia, setOverlayGaia] = useState(false);
  const [overlayWise, setOverlayWise] = useState(false);
  const [overlays, setOverlays] = useState<OverlaySet | null>(null);
  const [aladinOpen, setAladinOpen] = useState(false);
  const [glossaryOpen, setGlossaryOpen] = useState(false);

  const [tutorialDone, setTutorialDone] = useState<boolean>(initialTutorialDone);
  const [tutorialOpen, setTutorialOpen] = useState<boolean>(
    !initialTutorialDone && !(initialUrl.mode === "explorer" && initialUrl.ra && initialUrl.dec)
  );
  const [discoveryPoints, setDiscoveryPoints] = useState<number>(initialProgress.points);
  const [verdicts, setVerdicts] = useState<Record<string, SavedVerdict>>(initialProgress.verdicts);

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

  const [exploreProgress, setExploreProgress] = useState<ProgressEvent | null>(null);
  const [exploring, setExploring] = useState(false);
  const [exploreError, setExploreError] = useState<string | null>(null);

  const cancelSseRef = useRef<(() => void) | null>(null);
  const packCacheRef = useRef<Record<string, DecodedFramepack>>({});
  const packOrderRef = useRef<string[]>([]);
  const sessionReqRef = useRef(0);
  const spectrumReqRef = useRef(0);

  const persistProgress = useCallback(
    (nextPoints: number, nextVerdicts: Record<string, SavedVerdict>) => {
      try {
        localStorage.setItem(
          PROGRESS_STORAGE_KEY,
          JSON.stringify({ points: nextPoints, verdicts: nextVerdicts })
        );
      } catch {
        // ignore storage quota failure
      }
    },
    []
  );

  const completeTutorial = useCallback(
    (awardBonus = false) => {
      setTutorialDone(true);
      setTutorialOpen(false);
      try {
        localStorage.setItem(TUTORIAL_STORAGE_KEY, "done");
      } catch {
        // ignore storage failure
      }
      if (awardBonus && !verdicts["tutorial_practice"]) {
        const nextV = {
          ...verdicts,
          tutorial_practice: { choice: "mover", matched: true, points: 50 },
        };
        const nextPts = discoveryPoints + 50;
        setVerdicts(nextV);
        setDiscoveryPoints(nextPts);
        persistProgress(nextPts, nextV);
      }
    },
    [discoveryPoints, persistProgress, verdicts]
  );

  const activePreset = useMemo(
    () => targets.find((t) => t.slug === activeMissionSlug) ?? null,
    [targets, activeMissionSlug]
  );

  const simpleCompare = useMemo(() => {
    if (!manifest) return null;
    const coaddPack = packs[`${manifest.session_id}:pass_coadds`];
    const diffPack = packs[`${manifest.session_id}:diffs`];
    return buildSimpleCompare(manifest, coaddPack, diffPack);
  }, [manifest, packs]);

  const activeProductKey = LENS_SPECS[lens].productKey;
  const activePack = useMemo(() => {
    if (!manifest) return null;
    if (lens === "blink") return simpleCompare?.blinkPack ?? null;
    return packs[`${manifest.session_id}:${activeProductKey}`] ?? null;
  }, [manifest, lens, simpleCompare, packs, activeProductKey]);

  const activeFrames = useMemo(() => {
    if (!manifest) return [];
    if (lens === "blink") return simpleCompare?.blinkMetas ?? [];
    const list = manifest.frames[activeProductKey] ?? [];
    if (lens === "visits" && detectorFilter !== null) {
      return list.filter((f) => f.detector === detectorFilter);
    }
    return list;
  }, [manifest, lens, simpleCompare, activeProductKey, detectorFilter]);

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

  const selectPattern = useCallback(
    async (cand: PatternCandidate) => {
      setActivePatternId(cand.id);
      if (cand.kind === "cold_ir") {
        setLensState("coldglow");
        setViewLayout("single");
      } else if (cand.kind === "mover") {
        setLensState("blink");
        setViewLayout("compare");
      } else if (cand.kind === "variable") {
        setLensState("blink");
        setViewLayout("compare");
      }
      await pickCoordinate(cand.ra, cand.dec, cand.fits_x, cand.fits_y);
    },
    [pickCoordinate]
  );

  const submitVerdict = useCallback(
    (cand: PatternCandidate, choice: string): SavedVerdict => {
      const key = `${manifest?.session_id ?? "session"}:${cand.id}`;
      const existing = verdicts[key];
      if (existing) return existing;

      const normalizedExpected =
        cand.kind === "archive_drift" ? "mover" : cand.kind;
      const matched = choice === normalizedExpected;
      const points = matched ? 35 : 15;
      const record: SavedVerdict = { choice, matched, points };
      const nextVerdicts = { ...verdicts, [key]: record };
      const nextPts = discoveryPoints + points;
      setVerdicts(nextVerdicts);
      setDiscoveryPoints(nextPts);
      persistProgress(nextPts, nextVerdicts);
      return record;
    },
    [discoveryPoints, manifest?.session_id, persistProgress, verdicts]
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
        while (packOrderRef.current.length > 14) {
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
    async (
      sess: SessionManifest,
      desiredLens: LensId,
      slug: string | null,
      reqId: number,
      desiredLayout?: ViewLayout
    ) => {
      if (reqId !== sessionReqRef.current) return;
      const specReq = ++spectrumReqRef.current;

      setManifest(sess);
      setOverlays(null);
      setPatterns(null);
      setActivePatternId(null);
      setPatternsLoading(true);
      setFrameIndexState(0);
      setPlaying(false);
      setLoOverride(null);
      setHiOverride(null);
      setDetectorFilter(null);
      setSessionError(null);

      let effectiveLens: LensId = desiredLens;
      if (effectiveLens === "blink" && !sess.products.pass_coadds) {
        effectiveLens = sess.products.coldglow ? "coldglow" : "visits";
      } else if (effectiveLens !== "blink") {
        const prodKey = LENS_SPECS[effectiveLens].productKey;
        if (!sess.products[prodKey]) {
          effectiveLens = sess.products.pass_coadds ? "blink" : "visits";
        }
      }
      setLensState(effectiveLens);
      setViewLayout(
        desiredLayout ?? (effectiveLens === "blink" ? "compare" : "single")
      );

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

      const overlaysPromise = fetchOverlays(
        sess.grid.ra0,
        sess.grid.dec0,
        sess.grid.fov_deg,
        mjdRef,
        slug
      )
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
          if (rep.candidates.length > 0) {
            setActivePatternId(rep.candidates[0].id);
          }
        })
        .catch(() => {
          if (reqId === sessionReqRef.current) setPatterns(null);
        })
        .finally(() => {
          if (reqId === sessionReqRef.current) setPatternsLoading(false);
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

      const productLoads: Promise<void>[] = [];
      if (effectiveLens === "blink") {
        productLoads.push(ensureProductLoaded(sess, "pass_coadds"));
        if (sess.products.diffs) {
          productLoads.push(ensureProductLoaded(sess, "diffs"));
        }
      } else {
        productLoads.push(ensureProductLoaded(sess, LENS_SPECS[effectiveLens].productKey));
      }

      await Promise.all([
        ...productLoads,
        overlaysPromise,
        patternsPromise,
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
        // Default citizen-friendly lens: Cold Heat for brown dwarf optical-dropouts, Past vs Present Compare for movers/variables
        const defaultLens: LensId =
          presetMeta?.default_lens === "coldglow" ? "coldglow" : "blink";
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
    (ra: string, dec: string, fov: number, targetLens: LensId = "blink") => {
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

  const setMode = useCallback(
    (nextMode: AppMode) => {
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
    },
    [activeMissionSlug, lens, manifest]
  );

  const setLens = useCallback(
    (nextLens: LensId) => {
      setLensState(nextLens);
      setFrameIndexState(0);
      setLoOverride(null);
      setHiOverride(null);
      setPlaying(false);
      if (nextLens !== "blink") {
        setViewLayout("single");
      }
      if (manifest) {
        if (nextLens === "blink") {
          ensureProductLoaded(manifest, "pass_coadds");
          if (manifest.products.diffs) ensureProductLoaded(manifest, "diffs");
        } else {
          ensureProductLoaded(manifest, LENS_SPECS[nextLens].productKey);
        }
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

  useFlipbookPlayback(playing && viewLayout === "single", fps, activeFrames.length, () => {
    stepFrame(1);
  });

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
          runExplore(url.ra, url.dec, url.fov ?? 0.05, url.lens ?? "blink");
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
            const defaultLens: LensId =
              url.lens ?? (presetMeta?.default_lens === "coldglow" ? "coldglow" : "blink");
            await applySessionManifest(sess, defaultLens, chosenSlug, reqId);
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

  const hunterRank = useMemo(() => getHunterRank(discoveryPoints), [discoveryPoints]);

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
      viewLayout,
      setViewLayout,
      simpleCompare,
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
      cleanMode,
      setCleanMode,
      crispPixels,
      setCrispPixels,
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
      tutorialDone,
      tutorialOpen,
      setTutorialOpen,
      completeTutorial,
      discoveryPoints,
      hunterRank,
      verdicts,
      patterns,
      patternsLoading,
      activePatternId,
      selectPattern,
      submitVerdict,
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
      viewLayout,
      simpleCompare,
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
      cleanMode,
      crispPixels,
      detectorFilter,
      overlayGaia,
      overlayWise,
      overlays,
      aladinOpen,
      glossaryOpen,
      tutorialDone,
      tutorialOpen,
      completeTutorial,
      discoveryPoints,
      hunterRank,
      verdicts,
      patterns,
      patternsLoading,
      activePatternId,
      selectPattern,
      submitVerdict,
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
