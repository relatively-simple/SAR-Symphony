import React, { useEffect, useMemo, useRef, useState } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import type { GeoFeatureOverlay, SignalId } from "../../api/types";
import { useAppState } from "../../state/store";

type BaseMapKind = "dark" | "satellite" | "topo";

const SIGNAL_META: Record<
  SignalId,
  { name: string; gibs: string; rgba: (norm: number, guard: boolean, flag: number) => [number, number, number, number] }
> = {
  temp: {
    name: "NASA MODIS Temp",
    gibs: "MODIS_Terra_CorrectedReflectance_TrueColor",
    rgba: (n) => [Math.round(180 + 75 * n), Math.round(70 + 130 * (1 - n)), Math.round(25 * (1 - n)), Math.round(45 + 150 * n)],
  },
  wind: {
    name: "NASA MERRA-2 Wind",
    gibs: "MODIS_Terra_CorrectedReflectance_TrueColor",
    rgba: (n) => [20, Math.round(150 + 85 * n), Math.round(190 + 55 * n), Math.round(40 + 145 * n)],
  },
  rain: {
    name: "NASA GPM Rain",
    gibs: "IMERG_Precipitation_Rate",
    rgba: (n) => [Math.round(30 + 30 * (1 - n)), Math.round(90 + 140 * n), 255, n < 0.08 ? 0 : Math.round(65 + 165 * n)],
  },
  optical: {
    name: "NASA MODIS Optical/NDVI",
    gibs: "MODIS_Terra_CorrectedReflectance_TrueColor",
    rgba: (n) => [Math.round(190 * (1 - n)), Math.round(120 + 115 * n), Math.round(75 * (1 - n)), Math.round(45 + 135 * n)],
  },
  radar: {
    name: "Sentinel-1 / NISAR SAR",
    gibs: "MODIS_Terra_CorrectedReflectance_TrueColor",
    rgba: (n, guard, flag) => {
      // Dark backscatter (< 0.35 normalized) -> floodwater / smooth ice highlight in cyan
      const hasIllusion = (flag & 0b01110) !== 0;
      if (hasIllusion && guard) {
        return [245, 158, 11, 210]; // Amber Guard highlight: deceptive echo corrected to water/truth
      }
      if (n < 0.35) {
        return [6, 182, 212, Math.round(195 - n * 240)];
      }
      return [148, 163, 184, Math.round(35 + n * 75)];
    },
  },
  nightlights: {
    name: "NASA Black Marble",
    gibs: "VIIRS_SNPP_DayNightBand_At_Sensor_Radiance",
    rgba: (n) => [250, Math.round(195 * n + 40), Math.round(35 * n), n < 0.12 ? 30 : Math.round(70 + 170 * n)],
  },
};

const BASE_TILES: Record<BaseMapKind, { label: string; url: string; attr: string }> = {
  dark: {
    label: "Dark Atlas",
    url: "https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}",
    attr: "Tiles &copy; Esri &mdash; Esri, DeLorme, NAVTEQ",
  },
  satellite: {
    label: "Satellite",
    url: "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
    attr: "Tiles &copy; Esri & Earthstar",
  },
  topo: {
    label: "Terrain",
    url: "https://server.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{z}/{y}/{x}",
    attr: "Tiles &copy; Esri",
  },
};

function clampGibsDate(raw?: string | null): string {
  // NASA GIBS Best archive has multi-day lag and no future dates; cap within proven GIBS coverage.
  const maxArchiveDate = "2025-11-24";
  const minArchiveDate = "2015-01-01";
  if (!raw || raw.length < 10) return "2024-11-24";
  const d = raw.slice(0, 10);
  if (d > maxArchiveDate) return maxArchiveDate;
  if (d < minArchiveDate) return minArchiveDate;
  return d;
}

export const StoryMapCanvas: React.FC = () => {
  const {
    manifest,
    packs,
    activeSceneIndex,
    activeLayers,
    frameIndex,
    illusionGuard,
    setIllusionGuard,
    selectedCoord,
    pickCoordinate,
    selectStoryScene,
    sessionLoading,
    exploring,
  } = useAppState();

  const mapHostRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<L.Map | null>(null);
  const baseLayerRef = useRef<L.TileLayer | null>(null);
  const gibsLayerRef = useRef<L.TileLayer | null>(null);
  const featureGroupRef = useRef<L.LayerGroup | null>(null);
  const rasterOverlayRef = useRef<L.ImageOverlay | null>(null);
  const clickMarkerRef = useRef<L.CircleMarker | null>(null);
  const flowCanvasRef = useRef<HTMLCanvasElement | null>(null);
  const lastCamKeyRef = useRef<string>("");

  const [baseKind, setBaseKind] = useState<BaseMapKind>("dark");
  const [gibsEnabled, setGibsEnabled] = useState<boolean>(true);
  const [swipeActive, setSwipeActive] = useState<boolean>(false);
  const [swipePct, setSwipePct] = useState<number>(50);
  const [dataOpacity, setDataOpacity] = useState<number>(0.72);

  const scenes = manifest?.story_scenes ?? [];
  const activeScene = scenes[activeSceneIndex] ?? scenes[0] ?? null;
  const primarySignal: SignalId = (activeLayers[0] as SignalId) || "radar";
  const centerLat = manifest?.target.lat ?? manifest?.grid.dec0 ?? 7.2906;
  const centerLon = manifest?.target.lon ?? manifest?.grid.ra0 ?? 80.6337;

  // Store callback refs for map clicks without reinitializing map
  const pickRef = useRef(pickCoordinate);
  pickRef.current = pickCoordinate;
  const manifestRef = useRef(manifest);
  manifestRef.current = manifest;

  // 1. Initialize Leaflet Map once
  useEffect(() => {
    const el = mapHostRef.current;
    if (!el || mapRef.current) return;

    const map = L.map(el, {
      center: [centerLat, centerLon],
      zoom: 7,
      zoomControl: false,
      attributionControl: true,
    });
    L.control.zoom({ position: "bottomright" }).addTo(map);

    const tile = L.tileLayer(BASE_TILES.dark.url, {
      attribution: BASE_TILES.dark.attr,
      maxNativeZoom: 16,
      maxZoom: 18,
    }).addTo(map);
    baseLayerRef.current = tile;

    const group = L.layerGroup().addTo(map);
    featureGroupRef.current = group;

    map.on("click", (ev: L.LeafletMouseEvent) => {
      const curManifest = manifestRef.current;
      const lat = ev.latlng.lat;
      const lon = ((((ev.latlng.lng + 180) % 360) + 360) % 360) - 180;
      let px: number | undefined;
      let py: number | undefined;
      if (curManifest) {
        const half = (curManifest.grid.fov_deg || 0.5) * 0.5;
        const n = curManifest.grid.npix || 64;
        px = Math.max(0, Math.min(n - 1, Math.round(((lon - (curManifest.grid.ra0 - half)) / (2 * half)) * (n - 1))));
        py = Math.max(0, Math.min(n - 1, Math.round(((lat - (curManifest.grid.dec0 - half)) / (2 * half)) * (n - 1))));
      }
      void pickRef.current(Number(lon.toFixed(4)), Number(lat.toFixed(4)), px, py);
    });

    mapRef.current = map;

    const ro = new ResizeObserver(() => {
      map.invalidateSize({ animate: false });
    });
    ro.observe(el);

    return () => {
      ro.disconnect();
      map.remove();
      mapRef.current = null;
    };
  }, []);

  // 2. Switch Base Map tiles cleanly
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    if (baseLayerRef.current) {
      map.removeLayer(baseLayerRef.current);
    }
    const spec = BASE_TILES[baseKind];
    baseLayerRef.current = L.tileLayer(spec.url, {
      attribution: spec.attr,
      maxNativeZoom: 16,
      maxZoom: 18,
    }).addTo(map);
    baseLayerRef.current.bringToBack();
  }, [baseKind]);

  // 3. Synchronize NASA GIBS WMTS satellite imagery overlay for current scene + active primary layer
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    if (gibsLayerRef.current) {
      map.removeLayer(gibsLayerRef.current);
      gibsLayerRef.current = null;
    }
    if (!gibsEnabled || !manifest) return;

    const rawGibsLayer =
      primarySignal === "rain"
        ? "IMERG_Precipitation_Rate"
        : primarySignal === "nightlights"
          ? "VIIRS_SNPP_DayNightBand_At_Sensor_Radiance"
          : activeScene?.gibs_layer || SIGNAL_META[primarySignal].gibs;
    const gibsLayerId =
      rawGibsLayer === "VIIRS_SNPP_DayNightBand_ENCC"
        ? "VIIRS_SNPP_DayNightBand_At_Sensor_Radiance"
        : rawGibsLayer;
    const gibsDate = clampGibsDate(
      manifest.event_dates?.[frameIndex] || activeScene?.gibs_date
    );
    const isImerg = gibsLayerId.includes("IMERG");
    const isDnb = gibsLayerId.includes("DayNightBand");
    const ext = isImerg || isDnb ? "png" : "jpg";
    const maxNative = isImerg ? 6 : isDnb ? 8 : 9;
    const tileMatrix = `GoogleMapsCompatible_Level${maxNative}`;
    const url = `https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/${gibsLayerId}/default/${gibsDate}/${tileMatrix}/{z}/{y}/{x}.${ext}`;

    const gibs = L.tileLayer(url, {
      opacity: primarySignal === "rain" ? 0.65 : 0.45,
      maxNativeZoom: maxNative,
      maxZoom: 16,
      attribution: "NASA GIBS EOSDIS",
      errorTileUrl: "",
    });
    gibs.on("tileerror", () => {
      // Suppress noisy console rejection on high zoom or cloud-gap tiles
    });
    gibs.addTo(map);
    gibsLayerRef.current = gibs;
  }, [gibsEnabled, manifest, primarySignal, activeScene, frameIndex]);

  // 4. Smooth Multi-Scale Camera Flight when Event or Story Scene changes
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !manifest) return;
    const cam = activeScene?.camera;
    const targetLat = cam?.lat ?? centerLat;
    const targetLon = cam?.lon ?? centerLon;
    const targetZoom = cam?.zoom ?? 9.5;
    const camKey = `${manifest.session_id}:${activeSceneIndex}:${targetLat.toFixed(3)}:${targetLon.toFixed(3)}:${targetZoom}`;
    if (camKey === lastCamKeyRef.current) return;
    lastCamKeyRef.current = camKey;
    map.flyTo([targetLat, targetLon], targetZoom, { duration: 1.25, easeLinearity: 0.25 });
  }, [manifest, activeScene, activeSceneIndex, centerLat, centerLon]);

  // 5. Render GeoFeature overlays (low pressure core, storm track, flood polygon, blackout rings, illusion guard polygon) + Domino markers
  useEffect(() => {
    const map = mapRef.current;
    const group = featureGroupRef.current;
    if (!map || !group || !manifest) return;
    group.clearLayers();

    const features: GeoFeatureOverlay[] = manifest.geo_features ?? [];
    for (const feat of features) {
      const inScene =
        !feat.scene_indices ||
        feat.scene_indices.length === 0 ||
        feat.scene_indices.includes(activeSceneIndex);
      const isIllusion = feat.kind.startsWith("illusion");
      const opacityFactor = inScene ? 1.0 : 0.25;
      const strokeColor = isIllusion && !illusionGuard ? "#94a3b8" : feat.color;

      const popupHtml = `
        <div style="font-size:12px;line-height:1.4;max-width:240px;">
          <strong style="color:${strokeColor}">${feat.label}</strong>
          <div style="margin-top:4px;color:#334155;">${feat.detail}</div>
          ${isIllusion ? `<div style="margin-top:4px;font-weight:700;color:#b45309;">${illusionGuard ? "AI Guard ON: True water/surface mask restored" : "AI Guard OFF: Raw ambiguous SAR echo shown"}</div>` : ""}
        </div>
      `;

      if (feat.geometry_type === "polygon" && Array.isArray(feat.coordinates)) {
        const poly = L.polygon(feat.coordinates as [number, number][], {
          color: strokeColor,
          weight: inScene ? 2.4 : 1.1,
          dashArray: isIllusion ? "6 4" : undefined,
          fillColor: strokeColor,
          fillOpacity: isIllusion
            ? illusionGuard
              ? 0.28 * opacityFactor
              : 0.08 * opacityFactor
            : 0.24 * opacityFactor,
        }).bindPopup(popupHtml);
        group.addLayer(poly);
      } else if (feat.geometry_type === "polyline" && Array.isArray(feat.coordinates)) {
        const line = L.polyline(feat.coordinates as [number, number][], {
          color: strokeColor,
          weight: inScene ? 3.5 : 1.5,
          dashArray: "8 6",
          opacity: 0.88 * opacityFactor,
        }).bindPopup(popupHtml);
        group.addLayer(line);
      } else if (
        (feat.geometry_type === "point_radius" || feat.geometry_type === "point") &&
        Array.isArray(feat.coordinates) &&
        feat.coordinates.length >= 2
      ) {
        const pt = feat.coordinates as [number, number];
        const radiusMeters = Math.max(1500, (feat.radius_km || 18) * 1000);
        const circle = L.circle(pt, {
          radius: radiusMeters,
          color: strokeColor,
          weight: inScene ? 2 : 1,
          fillColor: strokeColor,
          fillOpacity: 0.16 * opacityFactor,
        }).bindPopup(popupHtml);
        group.addLayer(circle);
      }
    }

    // Numbered Domino Step Waypoints along the Story Scenes
    const STEP_COLORS = ["#f97316", "#14b8a6", "#3b82f6", "#a855f7", "#f43f5e"];
    scenes.forEach((sc, idx) => {
      if (!sc.camera) return;
      const isCurrent = idx === activeSceneIndex;
      const stepColor = STEP_COLORS[idx % STEP_COLORS.length];
      const badgeIcon = L.divIcon({
        className: "domino-map-pin-wrap",
        html: `<div class="domino-map-pin ${isCurrent ? "active" : ""}" style="border-color:${stepColor};${isCurrent ? `background:${stepColor};box-shadow:0 0 14px ${stepColor};` : `color:${stepColor};`}" title="Step ${idx + 1}: ${sc.title}">${idx + 1}</div>`,
        iconSize: [26, 26],
        iconAnchor: [13, 13],
      });
      const marker = L.marker([sc.camera.lat, sc.camera.lon], { icon: badgeIcon });
      marker.on("click", () => selectStoryScene(idx));
      marker.bindTooltip(`${idx + 1}. ${sc.phase}: ${sc.title}`, { direction: "top", offset: [0, -10] });
      group.addLayer(marker);
    });
  }, [manifest, scenes, activeSceneIndex, illusionGuard, selectStoryScene]);

  // 6. Render Georeferenced Multi-Sensor Cube Canvas Overlay (with Before vs Peak Split Swipe & Illusion Guard)
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !manifest) return;
    if (rasterOverlayRef.current) {
      map.removeLayer(rasterOverlayRef.current);
      rasterOverlayRef.current = null;
    }

    const pack = packs[`${manifest.session_id}:${primarySignal}`];
    if (!pack || pack.nFrames === 0) return;

    const npix = pack.npix;
    const planeStride = npix * npix;
    const frameStride = pack.planesPerFrame * planeStride;
    const canvas = document.createElement("canvas");
    canvas.width = npix;
    canvas.height = npix;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const curIdx = Math.max(0, Math.min(pack.nFrames - 1, frameIndex));
    const baseIdx = 0;
    const curFrame = pack.data.subarray(curIdx * frameStride, curIdx * frameStride + planeStride);
    const baseFrame = pack.data.subarray(baseIdx * frameStride, baseIdx * frameStride + planeStride);
    const curFlags = pack.flags ? pack.flags.subarray(curIdx * planeStride, (curIdx + 1) * planeStride) : null;
    const radarPack = packs[`${manifest.session_id}:radar`];
    const radarFlags =
      radarPack?.flags && curIdx < radarPack.nFrames && radarPack.npix === npix
        ? radarPack.flags.subarray(curIdx * planeStride, (curIdx + 1) * planeStride)
        : null;
    if (curFrame.length < planeStride || baseFrame.length < planeStride) return;

    // Robust percentile min/max over active frame + baseline
    let minV = Infinity;
    let maxV = -Infinity;
    for (let i = 0; i < curFrame.length; i++) {
      const a = curFrame[i];
      const b = baseFrame[i];
      if (Number.isFinite(a)) {
        if (a < minV) minV = a;
        if (a > maxV) maxV = a;
      }
      if (Number.isFinite(b)) {
        if (b < minV) minV = b;
        if (b > maxV) maxV = b;
      }
    }
    const span = Math.max(1e-4, maxV - minV);
    const imgData = ctx.createImageData(npix, npix);
    const swipeCol = Math.round((swipePct / 100) * npix);
    const colorFn = SIGNAL_META[primarySignal].rgba;

    for (let row = 0; row < npix; row++) {
      const flippedY = npix - 1 - row;
      for (let col = 0; col < npix; col++) {
        const useBaseline = swipeActive && col < swipeCol;
        const pIdx = flippedY * npix + col;
        const val = useBaseline ? baseFrame[pIdx] : curFrame[pIdx];
        const flagVal = useBaseline ? 0 : (radarFlags?.[pIdx] ?? curFlags?.[pIdx] ?? 0);
        const norm = Number.isFinite(val) ? Math.max(0, Math.min(1, (val - minV) / span)) : 0;
        const [r, g, b, a] = colorFn(norm, illusionGuard, flagVal);
        const outIdx = (row * npix + col) * 4;
        imgData.data[outIdx] = r;
        imgData.data[outIdx + 1] = g;
        imgData.data[outIdx + 2] = b;
        imgData.data[outIdx + 3] = a;
      }
    }
    ctx.putImageData(imgData, 0, 0);

    // Draw split divider line right onto image when Swipe is enabled
    if (swipeActive) {
      ctx.strokeStyle = "#ffffff";
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(swipeCol + 0.5, 0);
      ctx.lineTo(swipeCol + 0.5, npix);
      ctx.stroke();
    }

    const halfFov = Math.max(0.2, manifest.grid.fov_deg * 0.5);
    const cLat = manifest.grid.dec0;
    const cLon = manifest.grid.ra0;
    const bounds = L.latLngBounds(
      [cLat - halfFov, cLon - halfFov],
      [cLat + halfFov, cLon + halfFov]
    );

    const overlay = L.imageOverlay(canvas.toDataURL(), bounds, {
      opacity: dataOpacity,
      interactive: false,
    }).addTo(map);
    rasterOverlayRef.current = overlay;
  }, [manifest, packs, primarySignal, frameIndex, swipeActive, swipePct, illusionGuard, dataOpacity]);

  // 7. Show clicked pixel crosshair ring on Leaflet
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    if (clickMarkerRef.current) {
      map.removeLayer(clickMarkerRef.current);
      clickMarkerRef.current = null;
    }
    if (!selectedCoord) return;
    clickMarkerRef.current = L.circleMarker([selectedCoord.dec, selectedCoord.ra], {
      radius: 8,
      color: "#ffffff",
      weight: 2,
      fillColor: "#38bdf8",
      fillOpacity: 0.45,
    })
      .bindTooltip(`Sampled: ${selectedCoord.dec.toFixed(3)}°, ${selectedCoord.ra.toFixed(3)}°`)
      .addTo(map);
  }, [selectedCoord]);

  // 8. Animated Wind & Causal Flow Particles Layer synced to Leaflet view transform
  const flowPaths = useMemo(() => {
    const ptsList: [number, number][][] = [];
    if (manifest?.geo_features) {
      for (const feat of manifest.geo_features) {
        if (feat.geometry_type === "polyline" && Array.isArray(feat.coordinates) && feat.coordinates.length >= 2) {
          ptsList.push(feat.coordinates as [number, number][]);
        }
      }
    }
    if (ptsList.length === 0 && activeScene?.causal_chain) {
      for (const link of activeScene.causal_chain) {
        if (link.from_coord && link.to_coord) {
          ptsList.push([link.from_coord, link.to_coord]);
        }
      }
    }
    if (ptsList.length === 0 && scenes.length >= 2) {
      const coords = scenes
        .map((s) => (s.camera ? ([s.camera.lat, s.camera.lon] as [number, number]) : null))
        .filter((c): c is [number, number] => Boolean(c));
      if (coords.length >= 2) ptsList.push(coords);
    }
    return ptsList;
  }, [manifest?.geo_features, activeScene, scenes]);

  useEffect(() => {
    const canvas = flowCanvasRef.current;
    const map = mapRef.current;
    if (!canvas || !map) return;

    const particles = Array.from({ length: 56 }, (_, i) => ({
      t: (i % 28) / 28,
      pathIdx: i % Math.max(1, flowPaths.length),
      lateral: ((i % 7) - 3) * 7,
      speed: 0.0045 + (i % 5) * 0.0008,
    }));

    let rafId = 0;
    const render = () => {
      const size = map.getSize();
      if (canvas.width !== size.x || canvas.height !== size.y) {
        canvas.width = size.x;
        canvas.height = size.y;
      }
      const ctx = canvas.getContext("2d");
      if (ctx) {
        ctx.clearRect(0, 0, canvas.width, canvas.height);

        // Subtle ambient wind advection particles + glowing domino corridor streamlines
        if (flowPaths.length > 0) {
          for (const p of particles) {
            const path = flowPaths[p.pathIdx % flowPaths.length];
            if (!path || path.length < 2) continue;
            p.t = (p.t + p.speed) % 1;
            const segFloat = p.t * (path.length - 1);
            const segIdx = Math.min(path.length - 2, Math.floor(segFloat));
            const frac = segFloat - segIdx;
            const [lat1, lon1] = path[segIdx];
            const [lat2, lon2] = path[segIdx + 1];
            const ptA = map.latLngToContainerPoint([lat1, lon1]);
            const ptB = map.latLngToContainerPoint([lat2, lon2]);
            const dx = ptB.x - ptA.x;
            const dy = ptB.y - ptA.y;
            const len = Math.max(1, Math.hypot(dx, dy));
            const nx = -dy / len;
            const ny = dx / len;
            const cx = ptA.x + dx * frac + nx * p.lateral;
            const cy = ptA.y + dy * frac + ny * p.lateral;
            const prevFrac = Math.max(0, frac - 0.06);
            const px = ptA.x + dx * prevFrac + nx * p.lateral;
            const py = ptA.y + dy * prevFrac + ny * p.lateral;

            ctx.strokeStyle =
              primarySignal === "temp"
                ? "rgba(251, 146, 60, 0.85)"
                : primarySignal === "rain"
                  ? "rgba(96, 165, 250, 0.88)"
                  : "rgba(56, 189, 248, 0.85)";
            ctx.lineWidth = 2.2;
            ctx.lineCap = "round";
            ctx.beginPath();
            ctx.moveTo(px, py);
            ctx.lineTo(cx, cy);
            ctx.stroke();

            ctx.fillStyle = "#ffffff";
            ctx.beginPath();
            ctx.arc(cx, cy, 1.8, 0, Math.PI * 2);
            ctx.fill();
          }
        }
      }
      rafId = window.requestAnimationFrame(render);
    };

    rafId = window.requestAnimationFrame(render);
    return () => window.cancelAnimationFrame(rafId);
  }, [flowPaths, primarySignal]);

  const currentDate = manifest?.event_dates?.[frameIndex] || activeScene?.date_label || "";

  return (
    <div className="story-map-stage">
      {/* Interactive Leaflet Map */}
      <div ref={mapHostRef} className="leaflet-map-host" />

      {/* Animated Wind & Cause-to-Effect Streamline Canvas */}
      <canvas ref={flowCanvasRef} className="flow-particle-canvas" />

      {/* Top-Left Camera & Active NASA Datasets HUD */}
      <div className="map-hud-topleft">
        <div className="map-hud-title">
          <span className="phase-chip">
            Step {activeSceneIndex + 1}/5 · {activeScene?.phase || "Story"}
          </span>
          <span className="mono date-chip">{currentDate}</span>
        </div>
        <div className="map-hud-region">
          {activeScene?.camera?.region_name || manifest?.region_label || "Loading region..."}
        </div>
        <div className="map-hud-meta mono">
          {centerLat >= 0 ? `${centerLat.toFixed(2)}°N` : `${Math.abs(centerLat).toFixed(2)}°S`},{" "}
          {centerLon >= 0 ? `${centerLon.toFixed(2)}°E` : `${Math.abs(centerLon).toFixed(2)}°W`} · Primary:{" "}
          {SIGNAL_META[primarySignal].name}
        </div>
      </div>

      {/* Top-Right Interactive Controls HUD */}
      <div className="map-hud-topright">
        <div className="hud-seg-group" role="group" aria-label="Base map">
          {(Object.keys(BASE_TILES) as BaseMapKind[]).map((k) => (
            <button
              key={k}
              type="button"
              className={`hud-btn ${baseKind === k ? "active" : ""}`}
              onClick={() => setBaseKind(k)}
            >
              {BASE_TILES[k].label}
            </button>
          ))}
        </div>

        <button
          type="button"
          className={`hud-btn ${gibsEnabled ? "active hud-amber" : ""}`}
          onClick={() => setGibsEnabled((v) => !v)}
          title="Toggle live NASA GIBS EOSDIS satellite tiles"
        >
          🛰️ GIBS {gibsEnabled ? "ON" : "OFF"}
        </button>

        <button
          type="button"
          className={`hud-btn ${illusionGuard ? "active hud-emerald" : ""}`}
          onClick={() => setIllusionGuard(!illusionGuard)}
          title="Toggle AI Multi-Sensor Guard separating wind waves & flash-freeze artifacts"
        >
          🛡️ Guard {illusionGuard ? "ON" : "OFF"}
        </button>

        <button
          type="button"
          className={`hud-btn ${swipeActive ? "active hud-violet" : ""}`}
          onClick={() => setSwipeActive((v) => !v)}
          title="Compare Baseline Pass 1 vs Selected Timestamp"
        >
          ↔ Split
        </button>
      </div>

      {/* Bottom Swipe Comparison & Opacity Bar (when swipe or slider open) */}
      {swipeActive && (
        <div className="map-swipe-bar">
          <span className="mono">Before ({manifest?.event_dates?.[0] || "Day 1"})</span>
          <input
            type="range"
            min={10}
            max={90}
            value={swipePct}
            onChange={(e) => setSwipePct(Number(e.target.value))}
            aria-label="Before and peak split slider"
          />
          <span className="mono">Active ({currentDate})</span>
        </div>
      )}

      {/* Draggable Vertical Swipe Guide */}
      {swipeActive && (
        <div className="map-swipe-divider" style={{ left: `${swipePct}%` }}>
          <div className="map-swipe-handle">↔</div>
        </div>
      )}

      {/* Subtle Map Opacity Control Bottom Left */}
      <div className="map-hud-bottomleft">
        <label className="mono">
          Overlay {Math.round(dataOpacity * 100)}%
          <input
            type="range"
            min={0.15}
            max={0.95}
            step={0.05}
            value={dataOpacity}
            onChange={(e) => setDataOpacity(Number(e.target.value))}
          />
        </label>
        <span className="map-click-hint">Click map to sample</span>
      </div>

      {(sessionLoading || exploring) && (
        <div className="map-loading-pill">
          Loading NASA satellite signals &amp; building Domino Chain...
        </div>
      )}
    </div>
  );
};
