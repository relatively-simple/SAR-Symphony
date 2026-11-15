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
import {
  SOLO_PRIMARY_SLUGS,
  TRAINING_DEMO_SLUG,
  TRAINING_STORAGE_KEY_V2,
  TRAINING_TESTS,
  type TrainingPhase,
} from "../content/training";
import { decodeFramepack, type DecodedFramepack } from "../engine/framepack";
import { useFlipbookPlayback } from "../engine/player";
import { buildSimpleCompare, type SimpleCompareData } from "../engine/simpleCompare";
import { readUrlState, writeUrlState } from "./url";

export type AppMode = "missions" | "explorer";

export interface SavedVerdict {
  choice: string;
  matched: boolean;
  points: number;
  expectedSummary?: string;
}

export interface TestChecklist {
  action1Done: boolean;
  action2Done: boolean;
  testPassed: boolean;
  feedback: { ok: boolean; text: string } | null;
}

interface StoredTrainingState {
  phase: TrainingPhase;
  demoRewarded: boolean;
  test1Passed: boolean;
  test2Passed: boolean;
}

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

function loadSavedTraining(): StoredTrainingState {
  try {
    const raw = localStorage.getItem(TRAINING_STORAGE_KEY_V2);
    if (!raw) {
      return {
        phase: "round1-demo",
        demoRewarded: false,
        test1Passed: false,
        test2Passed: false,
      };
    }
    const parsed = JSON.parse(raw);
    const validPhases: TrainingPhase[] = ["round1-demo", "round2-test1", "round2-test2", "solo"];
    const phase = validPhases.includes(parsed.phase) ? parsed.phase : "round1-demo";
    return {
      phase,
      demoRewarded: Boolean(parsed.demoRewarded),
      test1Passed: Boolean(parsed.test1Passed),
      test2Passed: Boolean(parsed.test2Passed),
    };
  } catch {
    return {
      phase: "round1-demo",
      demoRewarded: false,
      test1Passed: false,
      test2Passed: false,
    };
  }
}

export function getHunterRank(points: number): string {
  if (points >= 220) return "Planet X Pioneer";
  if (points >= 120) return "Pattern Analyst";
  if (points >= 50) return "Sky Spotter";
  return "Curious Explorer";
}

const EMPTY_CHECKLIST: TestChecklist = {
  action1Done: false,
  action2Done: false,
  testPassed: false,
  feedback: null,
};

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

  // 2-Round Real-Data Training & Unassisted Solo Mode
  trainingPhase: TrainingPhase;
  autoDemoStep: 0 | 1 | 2 | 3;
  setAutoDemoStep: (step: 0 | 1 | 2 | 3) => void;
  demoPaused: boolean;
  setDemoPaused: (p: boolean) => void;
  demoDone: boolean;
  testChecklist: TestChecklist;
  canRevealPattern: boolean;
  soloRevealOverride: boolean;
  toggleSoloReveal: () => void;
  replayTraining: () => void;
  skipTraining: () => void;
  advanceFromDemoToTest1: () => void;
  advanceFromTest1ToTest2: () => void;
  graduateToSolo: () => void;
  submitTrainingVerdict: (choice: string) => void;
  submitSoloVerdict: (choice: string) => SavedVerdict | null;

  discoveryPoints: number;
  hunterRank: string;
  verdicts: Record<string, SavedVerdict>;
  patterns: PatternReport | null;
  patternsLoading: boolean;
  activePatternId: string | null;
  selectPattern: (cand: PatternCandidate) => Promise<void>;

  selectedCoord: { ra: number; dec: number; x?: number; y?: number } | null;
  pickCoordinate: (
    ra: number,
    dec: number,
    x?: number,
    y?: number,
    isUserClick?: boolean,
    panelKind?: "past" | "present" | "diff"
  ) => Promise<void>;
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
  const initialTraining = useMemo(() => loadSavedTraining(), []);
  const initialUrl = useMemo(() => readUrlState(), []);

  // Direct Explorer URL deep-links bypass the landing training gate
  const bypassToExplorer =
    initialUrl.mode === "explorer" && Boolean(initialUrl.ra) && Boolean(initialUrl.dec);

  const [targets, setTargets] = useState<TargetPreset[]>([]);
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [mode, setModeState] = useState<AppMode>(bypassToExplorer ? "explorer" : "missions");
  const [activeMissionSlug, setActiveMissionSlug] = useState<string | null>(null);
  const [manifest, setManifest] = useState<SessionManifest | null>(null);
  const [sessionLoading, setSessionLoading] = useState(false);
  const [sessionError, setSessionError] = useState<string | null>(null);

  const [packs, setPacks] = useState<Record<string, DecodedFramepack>>({});
  const [productLoading, setProductLoading] = useState(false);

  const [lens, setLensState] = useState<LensId>("blink");
  const [viewLayout, setViewLayoutState] = useState<ViewLayout>("compare");
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

  const [overlayGaia, setOverlayGaia] = useState(false);
  const [overlayWise, setOverlayWise] = useState(false);
  const [overlays, setOverlays] = useState<OverlaySet | null>(null);
  const [aladinOpen, setAladinOpen] = useState(false);
  const [glossaryOpen, setGlossaryOpen] = useState(false);

  const [trainingState, setTrainingState] = useState<StoredTrainingState>(() =>
    bypassToExplorer ? { ...initialTraining, phase: "solo" } : initialTraining
  );
  const trainingPhase = trainingState.phase;

  const [autoDemoStep, setAutoDemoStepState] = useState<0 | 1 | 2 | 3>(0);
  const [demoPaused, setDemoPaused] = useState(false);
  const [demoDone, setDemoDone] = useState(false);
  const [testChecklist, setTestChecklist] = useState<TestChecklist>(EMPTY_CHECKLIST);
  const [soloRevealOverride, setSoloRevealOverride] = useState(false);

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
        // ignore quota errors
      }
    },
    []
  );

  const persistTraining = useCallback((next: StoredTrainingState) => {
    setTrainingState(next);
    try {
      localStorage.setItem(TRAINING_STORAGE_KEY_V2, JSON.stringify(next));
    } catch {
      // ignore quota errors
    }
  }, []);

  const awardPointsOnce = useCallback(
    (key: string, choice: string, matched: boolean, points: number, expectedSummary?: string) => {
      if (verdicts[key]) return verdicts[key];
      const record: SavedVerdict = { choice, matched, points, expectedSummary };
      const nextVerdicts = { ...verdicts, [key]: record };
      const nextPts = discoveryPoints + points;
      setVerdicts(nextVerdicts);
      setDiscoveryPoints(nextPts);
      persistProgress(nextPts, nextVerdicts);
      return record;
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

  const pickCoordinate = useCallback(
    async (
      ra: number,
      dec: number,
      x?: number,
      y?: number,
      isUserClick = false,
      panelKind?: "past" | "present" | "diff"
    ) => {
      if (!manifest || !Number.isFinite(ra) || !Number.isFinite(dec)) return;
      const specReq = ++spectrumReqRef.current;
      setSelectedCoord({ ra, dec, x, y });

      // Validate hands-on actions during Round 2 training tests
      if (isUserClick && (trainingPhase === "round2-test1" || trainingPhase === "round2-test2")) {
        const spec = TRAINING_TESTS[trainingPhase];
        if (activeMissionSlug === spec.slug) {
          const dist =
            typeof x === "number" && typeof y === "number"
              ? Math.hypot(x - spec.targetX, y - spec.targetY)
              : 0;
          const nearTarget = dist <= spec.tolerancePx;

          if (trainingPhase === "round2-test1") {
            if (lens !== "coldglow") {
              setTestChecklist((prev) =>
                prev.testPassed
                  ? prev
                  : {
                      ...prev,
                      feedback: {
                        ok: false,
                        text: "First switch to Cold Glow (3.8–5.0 µm) in the lens bar so cold thermal sources appear clearly!",
                      },
                    }
              );
            } else if (nearTarget) {
              setTestChecklist((prev) => ({
                ...prev,
                action1Done: true,
                action2Done: true,
                feedback: prev.testPassed
                  ? prev.feedback
                  : {
                      ok: true,
                      text: "Target locked in Cold Glow! Inspect the rising 4.5 µm spectrum on the right, then classify what you found below.",
                    },
              }));
            } else {
              setTestChecklist((prev) =>
                prev.action2Done || prev.testPassed
                  ? prev
                  : {
                      ...prev,
                      feedback: {
                        ok: false,
                        text: "Close — click inside the faint white dashed circle near the center of Cold Glow to inspect the cold suspect.",
                      },
                    }
              );
            }
          } else if (trainingPhase === "round2-test2") {
            const inspectedByPanel = panelKind === "diff";
            if (nearTarget) {
              setTestChecklist((prev) => {
                const act1 = prev.action1Done || inspectedByPanel;
                return {
                  ...prev,
                  action1Done: act1,
                  action2Done: true,
                  feedback: prev.testPassed
                    ? prev.feedback
                    : {
                        ok: true,
                        text: act1
                          ? "Both viewer checks done! Review the sparkline & spectrum, then classify what happened below."
                          : "Nice click on the central star! Now also click Variable Watch or Difference Only (Step 1) to confirm brightness vs motion.",
                      },
                };
              });
            } else {
              setTestChecklist((prev) =>
                prev.action2Done || prev.testPassed
                  ? prev
                  : {
                      ...prev,
                      action1Done: prev.action1Done || inspectedByPanel,
                      feedback: {
                        ok: false,
                        text: "Click directly on the bright central star inside the faint white dashed circle.",
                      },
                    }
              );
            }
          }
        }
      }

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
    [activeMissionSlug, lens, manifest, trainingPhase]
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
      setSoloRevealOverride(false);
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
      setViewLayoutState(
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

  const selectMissionInternal = useCallback(
    async (slug: string, updateUrl = true) => {
      cancelSseRef.current?.();
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
        // Start every test & solo target cleanly on Past vs Present side-by-side without pre-spoiling the lens
        const defaultLens: LensId = "blink";
        await applySessionManifest(sess, defaultLens, slug, reqId, "compare");
        if (reqId === sessionReqRef.current && updateUrl) {
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
    [applySessionManifest]
  );

  const selectMission = useCallback(
    async (slug: string) => {
      await selectMissionInternal(slug, true);
    },
    [selectMissionInternal]
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
      if (trainingPhase !== "solo" && nextMode === "explorer") return;
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
    [activeMissionSlug, lens, manifest, trainingPhase]
  );

  const setViewLayout = useCallback(
    (v: ViewLayout) => {
      setViewLayoutState(v);
      if (
        trainingPhase === "round2-test2" &&
        activeMissionSlug === TRAINING_TESTS["round2-test2"].slug &&
        v === "single"
      ) {
        setTestChecklist((prev) => ({
          ...prev,
          action1Done: true,
          feedback:
            prev.action2Done || prev.testPassed
              ? prev.feedback
              : {
                  ok: true,
                  text: "Good — watching the star blink in place! Now click the central bright star (Step 2) to inspect it.",
                },
        }));
      }
    },
    [activeMissionSlug, trainingPhase]
  );

  const setLens = useCallback(
    (nextLens: LensId) => {
      setLensState(nextLens);
      setFrameIndexState(0);
      setLoOverride(null);
      setHiOverride(null);
      setPlaying(false);
      if (nextLens !== "blink") {
        setViewLayoutState("single");
      }

      if (
        trainingPhase === "round2-test1" &&
        activeMissionSlug === TRAINING_TESTS["round2-test1"].slug &&
        nextLens === "coldglow"
      ) {
        setTestChecklist((prev) => ({
          ...prev,
          action1Done: true,
          feedback: prev.action2Done || prev.testPassed
            ? prev.feedback
            : {
                ok: true,
                text: "Cold Glow active (3.8–5.0 µm)! Now click inside the faint white dashed circle near center to inspect the warm object.",
              },
        }));
      } else if (
        trainingPhase === "round2-test2" &&
        activeMissionSlug === TRAINING_TESTS["round2-test2"].slug &&
        (nextLens === "variable" || nextLens === "motion")
      ) {
        setTestChecklist((prev) => ({
          ...prev,
          action1Done: true,
          feedback: prev.action2Done || prev.testPassed
            ? prev.feedback
            : {
                ok: true,
                text: "Comparing brightness over time! Notice the central star doesn't jump across pixels. Now click it (Step 2) to inspect its spectrum.",
              },
        }));
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
    [activeMissionSlug, ensureProductLoaded, manifest, mode, trainingPhase]
  );

  // Automatic Step Sequence for Training Round 1 ("completely automatic")
  const applyDemoStepVisuals = useCallback(
    (step: 0 | 1 | 2 | 3) => {
      if (!manifest) return;
      if (step === 0) {
        setLensState("blink");
        setViewLayoutState("compare");
      } else if (step === 1) {
        ensureProductLoaded(manifest, "diffs");
        setLensState("motion");
        setViewLayoutState("single");
        setFrameIndexState(0);
      } else if (step === 2) {
        setLensState("blink");
        setViewLayoutState("compare");
        const cand = patterns?.candidates[0];
        if (cand) {
          pickCoordinate(cand.ra, cand.dec, cand.fits_x, cand.fits_y, false);
        } else {
          pickCoordinate(manifest.target.ra, manifest.target.dec, 13, 16, false);
        }
      } else if (step === 3) {
        setLensState("blink");
        setViewLayoutState("compare");
        setDemoDone(true);
        if (!trainingState.demoRewarded) {
          awardPointsOnce(
            "training:round1_demo",
            "mover",
            true,
            25,
            "Auto Demo Completed (Moving World)"
          );
          persistTraining({ ...trainingState, demoRewarded: true });
        }
      }
    },
    [
      awardPointsOnce,
      ensureProductLoaded,
      manifest,
      patterns?.candidates,
      persistTraining,
      pickCoordinate,
      trainingState,
    ]
  );

  const setAutoDemoStep = useCallback(
    (step: 0 | 1 | 2 | 3) => {
      setAutoDemoStepState(step);
      applyDemoStepVisuals(step);
    },
    [applyDemoStepVisuals]
  );

  useEffect(() => {
    if (
      trainingPhase !== "round1-demo" ||
      demoPaused ||
      demoDone ||
      activeMissionSlug !== TRAINING_DEMO_SLUG ||
      sessionLoading ||
      !manifest ||
      !simpleCompare
    ) {
      return;
    }

    if (autoDemoStep >= 3) return;
    if (autoDemoStep === 0) {
      applyDemoStepVisuals(0);
    }
    const nextStep = Math.min(3, autoDemoStep + 1) as 1 | 2 | 3;
    const timer = window.setTimeout(() => {
      setAutoDemoStepState(nextStep);
      applyDemoStepVisuals(nextStep);
    }, 3400);

    return () => window.clearTimeout(timer);
  }, [
    activeMissionSlug,
    applyDemoStepVisuals,
    autoDemoStep,
    demoDone,
    demoPaused,
    manifest,
    sessionLoading,
    simpleCompare,
    trainingPhase,
  ]);

  // Training transition actions
  const replayTraining = useCallback(() => {
    setAutoDemoStepState(0);
    setDemoPaused(false);
    setDemoDone(false);
    setTestChecklist(EMPTY_CHECKLIST);
    persistTraining({ ...trainingState, phase: "round1-demo" });
    selectMissionInternal(TRAINING_DEMO_SLUG, true);
  }, [persistTraining, selectMissionInternal, trainingState]);

  const advanceFromDemoToTest1 = useCallback(() => {
    setDemoPaused(true);
    setTestChecklist(EMPTY_CHECKLIST);
    persistTraining({ ...trainingState, phase: "round2-test1" });
    selectMissionInternal(TRAINING_TESTS["round2-test1"].slug, true);
  }, [persistTraining, selectMissionInternal, trainingState]);

  const advanceFromTest1ToTest2 = useCallback(() => {
    setTestChecklist(EMPTY_CHECKLIST);
    persistTraining({ ...trainingState, phase: "round2-test2" });
    selectMissionInternal(TRAINING_TESTS["round2-test2"].slug, true);
  }, [persistTraining, selectMissionInternal, trainingState]);

  const graduateToSolo = useCallback(() => {
    setTestChecklist(EMPTY_CHECKLIST);
    setSoloRevealOverride(false);
    persistTraining({ ...trainingState, phase: "solo" });
    const firstSolo = SOLO_PRIMARY_SLUGS[0];
    selectMissionInternal(firstSolo, true);
  }, [persistTraining, selectMissionInternal, trainingState]);

  const skipTraining = useCallback(() => {
    setDemoPaused(true);
    setTestChecklist(EMPTY_CHECKLIST);
    setSoloRevealOverride(false);
    persistTraining({ ...trainingState, phase: "solo" });
    selectMissionInternal(SOLO_PRIMARY_SLUGS[0], true);
  }, [persistTraining, selectMissionInternal, trainingState]);

  const submitTrainingVerdict = useCallback(
    (choice: string) => {
      if (trainingPhase !== "round2-test1" && trainingPhase !== "round2-test2") return;
      const spec = TRAINING_TESTS[trainingPhase];

      if (!testChecklist.action1Done || !testChecklist.action2Done) {
        setTestChecklist((prev) => ({
          ...prev,
          feedback: {
            ok: false,
            text: "Finish Steps 1 & 2 on the image viewer above before classifying so we confirm you inspected the target!",
          },
        }));
        return;
      }

      if (choice !== spec.expectedKind) {
        setTestChecklist((prev) => ({
          ...prev,
          feedback: {
            ok: false,
            text:
              spec.wrongHint[choice] ??
              "Not quite right — recheck the image panels and spectrum curve, then choose again!",
          },
        }));
        return;
      }

      // Passed!
      const isT1 = trainingPhase === "round2-test1";
      awardPointsOnce(
        isT1 ? "training:round2_test1" : "training:round2_test2",
        choice,
        true,
        50,
        spec.expectedLabel
      );
      persistTraining({
        ...trainingState,
        test1Passed: isT1 ? true : trainingState.test1Passed,
        test2Passed: !isT1 ? true : trainingState.test2Passed,
      });
      setTestChecklist({
        action1Done: true,
        action2Done: true,
        testPassed: true,
        feedback: { ok: true, text: spec.successNote },
      });
    },
    [awardPointsOnce, persistTraining, testChecklist.action1Done, testChecklist.action2Done, trainingPhase, trainingState]
  );

  const submitSoloVerdict = useCallback(
    (choice: string): SavedVerdict | null => {
      if (!manifest) return null;
      const key = manifest.session_id;
      if (verdicts[key]) return verdicts[key];

      const cands = patterns?.candidates ?? [];
      const accepted = new Set<string>();
      for (const c of cands) {
        accepted.add(c.kind === "archive_drift" ? "mover" : c.kind);
      }
      if (accepted.size === 0) accepted.add("artifact");

      const matched = accepted.has(choice);
      const pts = matched ? 35 : 15;
      const expectedSummary =
        cands.length > 0
          ? cands.map((c) => c.suggested_label).filter((v, i, a) => a.indexOf(v) === i).join(" / ")
          : "Static Sky / No Major Anomaly";

      return awardPointsOnce(key, choice, matched, pts, expectedSummary);
    },
    [awardPointsOnce, manifest, patterns?.candidates, verdicts]
  );

  const selectPattern = useCallback(
    async (cand: PatternCandidate) => {
      setActivePatternId(cand.id);
      await pickCoordinate(cand.ra, cand.dec, cand.fits_x, cand.fits_y, false);
    },
    [pickCoordinate]
  );

  const toggleSoloReveal = useCallback(() => {
    setSoloRevealOverride((v) => !v);
  }, []);

  const canRevealPattern = useMemo(() => {
    if (trainingPhase === "round1-demo") return autoDemoStep >= 1;
    if (trainingPhase === "round2-test1" || trainingPhase === "round2-test2") {
      return testChecklist.testPassed;
    }
    if (!manifest) return false;
    return Boolean(verdicts[manifest.session_id]) || soloRevealOverride;
  }, [
    autoDemoStep,
    manifest,
    soloRevealOverride,
    testChecklist.testPassed,
    trainingPhase,
    verdicts,
  ]);

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

        let startSlug: string | undefined;
        if (trainingState.phase === "round1-demo") {
          startSlug = TRAINING_DEMO_SLUG;
        } else if (trainingState.phase === "round2-test1") {
          startSlug = TRAINING_TESTS["round2-test1"].slug;
        } else if (trainingState.phase === "round2-test2") {
          startSlug = TRAINING_TESTS["round2-test2"].slug;
        } else {
          // Solo mode: prioritize remaining unassisted examples (Epsilon Indi B, R Draconis) unless URL explicitly chose one
          startSlug =
            url.mission && presetList.some((p) => p.slug === url.mission)
              ? url.mission
              : SOLO_PRIMARY_SLUGS.find((s) => presetList.some((p) => p.slug === s)) ??
                presetList[0]?.slug;
        }

        if (startSlug) {
          const reqId = ++sessionReqRef.current;
          setModeState("missions");
          setActiveMissionSlug(startSlug);
          setSessionLoading(true);
          try {
            const sess = await fetchTargetSession(startSlug);
            if (!alive || reqId !== sessionReqRef.current) return;
            await applySessionManifest(sess, "blink", startSlug, reqId, "compare");
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
    // Run once on initial mount
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

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
      trainingPhase,
      autoDemoStep,
      setAutoDemoStep,
      demoPaused,
      setDemoPaused,
      demoDone,
      testChecklist,
      canRevealPattern,
      soloRevealOverride,
      toggleSoloReveal,
      replayTraining,
      skipTraining,
      advanceFromDemoToTest1,
      advanceFromTest1ToTest2,
      graduateToSolo,
      submitTrainingVerdict,
      submitSoloVerdict,
      discoveryPoints,
      hunterRank,
      verdicts,
      patterns,
      patternsLoading,
      activePatternId,
      selectPattern,
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
      setViewLayout,
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
      trainingPhase,
      autoDemoStep,
      setAutoDemoStep,
      demoPaused,
      demoDone,
      testChecklist,
      canRevealPattern,
      soloRevealOverride,
      toggleSoloReveal,
      replayTraining,
      skipTraining,
      advanceFromDemoToTest1,
      advanceFromTest1ToTest2,
      graduateToSolo,
      submitTrainingVerdict,
      submitSoloVerdict,
      discoveryPoints,
      hunterRank,
      verdicts,
      patterns,
      patternsLoading,
      activePatternId,
      selectPattern,
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
