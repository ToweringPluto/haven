import "maplibre-gl/dist/maplibre-gl.css";
import {
  LngLatBounds,
  Map as MapLibreMap,
  Marker,
  NavigationControl,
  setWorkerUrl,
  type GeoJSONSource,
} from "maplibre-gl";
import workerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?url";
import { memo, useEffect, useRef, useState, type KeyboardEvent } from "react";
import { createPortal } from "react-dom";
import { Icon } from "../components/Icon";
import { formatGBP } from "../lib/format";
import { applyBrand, BASEMAP_STYLE, readBrandTokens, setBuildingRise, type BrandTokens } from "./brand";
import { arc, formatKm, midpoint, straightLineMetres, type LngLat } from "./geo";
import { STATE_COPY, type LensState } from "./lenses";
import { prefersReducedMotion, tween, useCountUp } from "./motion";

/** GeoJSON accepted by a GeoJSON source (avoids depending on @types/geojson directly). */
type FeatureCollection = Extract<Parameters<GeoJSONSource["setData"]>[0], { type: "FeatureCollection" }>;

// The bundle finds its worker next to itself, which breaks once Vite bundles it.
setWorkerUrl(workerUrl);

export interface PinView {
  id: string;
  lngLat: LngLat;
  title: string;
  area: string;
  price: number | null;
  /** True when the price is Haven's estimated total rather than the listed rent. */
  priceIsEstimate: boolean;
  state: LensState;
  /** Shown but de-emphasised (e.g. over the budget under the budget lens). */
  faded: boolean;
  saved: boolean;
  inCompare: boolean;
}

export interface PlaceView {
  name: string;
  lngLat: LngLat;
}

interface HavenMapProps {
  pins: PinView[];
  places: PlaceView[];
  selectedId: string | null;
  onSelect: (id: string | null) => void;
  compareIds: string[];
  /** Where the details panel opens, so the camera keeps the home in the visible part. */
  panel: "side" | "sheet";
  /** Bump to fly back to the overview. */
  overviewNonce: number;
  /** Called once, when the arrival flight has landed. */
  onArrived?: () => void;
}

// High over the Firth of Forth: where the arrival flight starts.
const INTRO_START = { center: [-3.08, 56.13] as LngLat, zoom: 8.6, pitch: 0, bearing: 0 };
const OVERVIEW_PITCH = 52;
const OVERVIEW_BEARING = -14;

const SRC_ARCS = "haven-arcs";
const SRC_ARC_LABELS = "haven-arc-labels";
const SRC_COMPARE = "haven-compare";

/** Ant-path frames for the animated dashes. */
const DASH_FRAMES: number[][] = [
  [0, 4, 3],
  [0.5, 4, 2.5],
  [1, 4, 2],
  [1.5, 4, 1.5],
  [2, 4, 1],
  [2.5, 4, 0.5],
  [3, 4, 0],
  [0, 0.5, 3, 3.5],
  [0, 1, 3, 3],
  [0, 1.5, 3, 2.5],
  [0, 2, 3, 2],
  [0, 2.5, 3, 1.5],
  [0, 3, 3, 1],
  [0, 3.5, 3, 0.5],
];

const empty = (): FeatureCollection => ({ type: "FeatureCollection", features: [] });

function addOverlayLayers(map: MapLibreMap, t: BrandTokens) {
  map.addSource(SRC_COMPARE, { type: "geojson", data: empty() });
  map.addSource(SRC_ARCS, { type: "geojson", data: empty() });
  map.addSource(SRC_ARC_LABELS, { type: "geojson", data: empty() });
  map.addLayer({
    id: "haven-compare-line",
    type: "line",
    source: SRC_COMPARE,
    layout: { "line-cap": "round", "line-join": "round" },
    paint: { "line-color": t.charcoal, "line-width": 2.5, "line-opacity": 0.75, "line-dasharray": [1, 2] },
  });
  map.addLayer({
    id: "haven-arcs-casing",
    type: "line",
    source: SRC_ARCS,
    layout: { "line-cap": "round" },
    paint: { "line-color": t.surface, "line-width": 7, "line-opacity": 0.85 },
  });
  map.addLayer({
    id: "haven-arcs-line",
    type: "line",
    source: SRC_ARCS,
    layout: { "line-cap": "butt" },
    paint: { "line-color": t.terracotta, "line-width": 3.5, "line-dasharray": DASH_FRAMES[0] },
  });
  map.addLayer({
    id: "haven-arc-labels",
    type: "symbol",
    source: SRC_ARC_LABELS,
    layout: {
      "text-field": ["get", "label"],
      "text-font": ["Noto Sans Regular"],
      "text-size": 12.5,
      "text-allow-overlap": true,
      "text-padding": 2,
    },
    paint: { "text-color": t.charcoal, "text-halo-color": t.surface, "text-halo-width": 2.2 },
  });
}

const setData = (map: MapLibreMap, id: string, data: FeatureCollection) =>
  (map.getSource(id) as GeoJSONSource | undefined)?.setData(data);

/** Camera that frames every home, pitched for the 3D city. */
function overviewCamera(map: MapLibreMap, pins: PinView[]) {
  const bounds = new LngLatBounds();
  pins.forEach((p) => bounds.extend(p.lngLat));
  const narrow = map.getContainer().clientWidth < 700;
  const cam = map.cameraForBounds(bounds, {
    padding: narrow
      ? { top: 150, bottom: 120, left: 40, right: 40 }
      : { top: 120, bottom: 120, left: 400, right: 120 },
    maxZoom: 13.6,
  });
  return { ...cam, pitch: OVERVIEW_PITCH, bearing: OVERVIEW_BEARING };
}

export function HavenMap({
  pins,
  places,
  selectedId,
  onSelect,
  compareIds,
  panel,
  overviewNonce,
  onArrived,
}: HavenMapProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const markersRef = useRef(new Map<string, Marker>());
  const placeMarkersRef = useRef(new Map<string, Marker>());
  const [pinEls, setPinEls] = useState<Record<string, HTMLElement>>({});
  const [placeEls, setPlaceEls] = useState<Record<string, HTMLElement>>({});
  const [loaded, setLoaded] = useState(false);
  const [arrived, setArrived] = useState(false);
  const pinsRef = useRef(pins);
  pinsRef.current = pins;
  const selectedRef = useRef(selectedId);
  selectedRef.current = selectedId;
  const onSelectRef = useRef(onSelect);
  onSelectRef.current = onSelect;
  const onArrivedRef = useRef(onArrived);
  onArrivedRef.current = onArrived;

  // --- the map itself (created once) ------------------------------------------------
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    const tokens = readBrandTokens();
    const map = new MapLibreMap({
      container,
      style: BASEMAP_STYLE,
      ...INTRO_START,
      maxPitch: 70,
      attributionControl: { compact: true },
      canvasContextAttributes: { antialias: true },
    });
    mapRef.current = map;
    map.addControl(new NavigationControl({ visualizePitch: true }), "top-right");
    map.on("style.load", () => {
      applyBrand(map, tokens);
      addOverlayLayers(map, tokens);
    });
    map.on("load", () => setLoaded(true));
    map.on("click", () => onSelectRef.current(null));

    const resize = new ResizeObserver(() => map.resize());
    resize.observe(container);
    return () => {
      resize.disconnect();
      map.remove();
      mapRef.current = null;
      markersRef.current.clear();
      placeMarkersRef.current.clear();
    };
  }, []);

  // --- arrival: fly in from the Forth, raise the buildings, drop the pins ---------------
  const introDone = useRef(false);
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !loaded || pins.length === 0 || introDone.current) return;
    introDone.current = true;
    const target = overviewCamera(map, pins);
    let cancelRise = () => {};
    const finish = () => {
      cancelRise = tween(1500, (k) => setBuildingRise(map, k));
      setArrived(true);
      onArrivedRef.current?.();
    };
    if (prefersReducedMotion()) {
      map.jumpTo(target);
      finish();
      return;
    }
    map.once("moveend", finish);
    map.flyTo({ ...target, duration: 4600, curve: 1.5, essential: false });
    return () => cancelRise();
  }, [loaded, pins.length]);

  // --- slow drift while idle, like a live map breathing ---------------------------------
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !arrived || prefersReducedMotion()) return;
    let lastInput = performance.now();
    const touched = () => (lastInput = performance.now());
    const events = ["mousedown", "touchstart", "wheel", "keydown"] as const;
    const canvas = map.getCanvasContainer();
    events.forEach((e) => canvas.addEventListener(e, touched, { passive: true }));
    const timer = window.setInterval(() => {
      const idle = performance.now() - lastInput > 12_000;
      if (!idle || selectedRef.current || map.isMoving() || document.hidden) return;
      map.easeTo({ bearing: map.getBearing() + 7, duration: 14_000, easing: (t) => t });
    }, 14_500);
    return () => {
      window.clearInterval(timer);
      events.forEach((e) => canvas.removeEventListener(e, touched));
    };
  }, [arrived]);

  // --- markers: one DOM element per home, rendered into by React portals ---------------
  const pinIds = pins.map((p) => p.id).join(",");
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const markers = markersRef.current;
    const wanted = new Set(pinsRef.current.map((p) => p.id));
    for (const [id, marker] of markers) {
      if (!wanted.has(id)) {
        marker.remove();
        markers.delete(id);
      }
    }
    for (const pin of pinsRef.current) {
      if (markers.has(pin.id)) continue;
      const el = document.createElement("div");
      el.className = "pin-anchor";
      markers.set(pin.id, new Marker({ element: el, anchor: "bottom" }).setLngLat(pin.lngLat).addTo(map));
    }
    setPinEls(Object.fromEntries([...markers].map(([id, m]) => [id, m.getElement()])));
  }, [pinIds, loaded]);

  useEffect(() => {
    for (const [id, marker] of markersRef.current) {
      marker.getElement().style.zIndex = id === selectedId ? "5" : compareIds.includes(id) ? "3" : "1";
    }
  }, [selectedId, compareIds, pinEls]);

  const placeKey = places.map((p) => p.name).join("|");
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const markers = placeMarkersRef.current;
    markers.forEach((m) => m.remove());
    markers.clear();
    for (const place of places) {
      const el = document.createElement("div");
      el.className = "place-anchor";
      markers.set(place.name, new Marker({ element: el, anchor: "bottom" }).setLngLat(place.lngLat).addTo(map));
    }
    setPlaceEls(Object.fromEntries([...markers].map(([name, m]) => [name, m.getElement()])));
  }, [placeKey, loaded]);

  // --- arcs from the selected home to the renter's places ------------------------------
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !loaded) return;
    const home = pins.find((p) => p.id === selectedId);
    const lines = home ? places.map((pl) => ({ pl, line: arc(home.lngLat, pl.lngLat) })) : [];
    setData(map, SRC_ARCS, {
      type: "FeatureCollection",
      features: lines.map(({ line }) => ({
        type: "Feature",
        properties: {},
        geometry: { type: "LineString", coordinates: line },
      })),
    });
    setData(map, SRC_ARC_LABELS, {
      type: "FeatureCollection",
      features: lines.map(({ pl, line }) => ({
        type: "Feature",
        properties: { label: `${formatKm(straightLineMetres(home!.lngLat, pl.lngLat))} straight line` },
        geometry: { type: "Point", coordinates: midpoint(line) },
      })),
    });
    if (lines.length === 0 || prefersReducedMotion()) return;
    let frame = 0;
    let step = 0;
    let last = 0;
    const animate = (now: number) => {
      if (now - last > 55) {
        last = now;
        step = (step + 1) % DASH_FRAMES.length;
        if (map.getLayer("haven-arcs-line")) {
          map.setPaintProperty("haven-arcs-line", "line-dasharray", DASH_FRAMES[step]);
        }
      }
      frame = requestAnimationFrame(animate);
    };
    frame = requestAnimationFrame(animate);
    return () => cancelAnimationFrame(frame);
    // Coordinates don't change for an id; `placeKey` captures the places.
  }, [selectedId, placeKey, loaded, pinIds]);

  // --- a dotted thread through the homes being compared --------------------------------
  const compareKey = compareIds.join(",");
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !loaded) return;
    const chosen = compareIds
      .map((id) => pinsRef.current.find((p) => p.id === id))
      .filter((p): p is PinView => !!p);
    const coords = chosen.flatMap((p, i) =>
      i === 0 ? [p.lngLat] : arc(chosen[i - 1].lngLat, p.lngLat, 0.12, 32).slice(1),
    );
    setData(map, SRC_COMPARE, {
      type: "FeatureCollection",
      features:
        coords.length > 1
          ? [{ type: "Feature", properties: {}, geometry: { type: "LineString", coordinates: coords } }]
          : [],
    });
    if (chosen.length >= 2 && !selectedRef.current && arrived) {
      const bounds = new LngLatBounds();
      chosen.forEach((p) => bounds.extend(p.lngLat));
      map.fitBounds(bounds, {
        padding: { top: 140, bottom: 260, left: 120, right: 120 },
        pitch: 40,
        maxZoom: 14.5,
        duration: prefersReducedMotion() ? 0 : 1600,
      });
    }
  }, [compareKey, loaded, arrived]);

  // --- camera follows the selection ----------------------------------------------------
  const hadSelection = useRef(false);
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !arrived) return;
    const pin = pinsRef.current.find((p) => p.id === selectedId);
    const duration = prefersReducedMotion() ? 0 : 1700;
    if (pin) {
      hadSelection.current = true;
      const width = map.getContainer().clientWidth;
      const height = map.getContainer().clientHeight;
      map.flyTo({
        center: pin.lngLat,
        zoom: Math.max(map.getZoom(), 15.3),
        pitch: 60,
        bearing: map.getBearing() + 18,
        offset: panel === "side" ? [-Math.min(460, width * 0.4) / 2, 40] : [0, -height * 0.22],
        duration,
        essential: false,
      });
    } else if (hadSelection.current) {
      hadSelection.current = false;
      map.flyTo({ ...overviewCamera(map, pinsRef.current), duration, essential: false });
    }
  }, [selectedId, arrived, panel]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !arrived || overviewNonce === 0) return;
    map.flyTo({ ...overviewCamera(map, pinsRef.current), duration: prefersReducedMotion() ? 0 : 1600 });
  }, [overviewNonce]);

  // Pins in west-to-east order, for arrow-key travel between them.
  const order = [...pins].sort((a, b) => a.lngLat[0] - b.lngLat[0]).map((p) => p.id);
  const focusPin = (from: string, delta: number) => {
    const next = order[(order.indexOf(from) + delta + order.length) % order.length];
    pinEls[next]?.querySelector("button")?.focus();
  };

  return (
    <div className={`haven-map${arrived ? " is-arrived" : ""}`}>
      <div ref={containerRef} className="haven-map-canvas" />
      {pins.map((pin) => {
        const el = pinEls[pin.id];
        return el
          ? createPortal(
              <PricePin
                pin={pin}
                index={order.indexOf(pin.id)}
                selected={pin.id === selectedId}
                onSelect={onSelect}
                onArrow={focusPin}
              />,
              el,
              pin.id,
            )
          : null;
      })}
      {places.map((place) => {
        const el = placeEls[place.name];
        return el ? createPortal(<PlacePin place={place} />, el, place.name) : null;
      })}
    </div>
  );
}

const PricePin = memo(function PricePin({
  pin,
  index,
  selected,
  onSelect,
  onArrow,
}: {
  pin: PinView;
  index: number;
  selected: boolean;
  onSelect: (id: string | null) => void;
  onArrow: (from: string, delta: number) => void;
}) {
  const shown = useCountUp(pin.price);
  const onKeyDown = (e: KeyboardEvent) => {
    if (e.key === "ArrowRight" || e.key === "ArrowDown") onArrow(pin.id, 1);
    else if (e.key === "ArrowLeft" || e.key === "ArrowUp") onArrow(pin.id, -1);
    else return;
    e.preventDefault();
  };
  const priceText =
    pin.price === null
      ? "price unknown"
      : `${formatGBP(pin.price)} ${pin.priceIsEstimate ? "estimated total a month" : "rent a month"}`;
  const classes = [
    "pin",
    `pin--${pin.state}`,
    pin.faded && "is-faded",
    selected && "is-selected",
    pin.inCompare && "is-compared",
  ]
    .filter(Boolean)
    .join(" ");
  return (
    <div className="pin-wrap" style={{ ["--i" as string]: index }}>
      <button
        type="button"
        className={classes}
        aria-pressed={selected}
        aria-label={`${pin.title}, ${pin.area}. ${priceText}. ${STATE_COPY[pin.state]}.`}
        onClick={(e) => {
          e.stopPropagation();
          onSelect(selected ? null : pin.id);
        }}
        onKeyDown={onKeyDown}
      >
        {pin.saved && <Icon name="heart" size={12} className="pin-heart" />}
        <span className="pin-price">{shown === null ? "—" : formatGBP(shown)}</span>
        {pin.priceIsEstimate && pin.price !== null && <span className="pin-est">est.</span>}
      </button>
      <span className="pin-stem" aria-hidden="true" />
      <span className="pin-pulse" aria-hidden="true" />
    </div>
  );
});

function PlacePin({ place }: { place: PlaceView }) {
  return (
    <div className="place-pin" title={place.name}>
      <Icon name="map" size={14} />
      <span>{place.name.replace(/,.*$/, "")}</span>
    </div>
  );
}
