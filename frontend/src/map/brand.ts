import type { Map as MapLibreMap } from "maplibre-gl";

/** OpenFreeMap's positron style: free OpenStreetMap vector tiles, no key. Repainted below. */
export const BASEMAP_STYLE = "https://tiles.openfreemap.org/styles/positron";

/** Haven's palette, read from the CSS tokens so the map can't drift from the rest of the app. */
export interface BrandTokens {
  teal: string;
  charcoal: string;
  terracotta: string;
  sage: string;
  cream: string;
  paper: string;
  surface: string;
  line: string;
  sageInk: string;
}

const FALLBACK: BrandTokens = {
  teal: "#006b6f",
  charcoal: "#2c2a2a",
  terracotta: "#c97c5d",
  sage: "#7aa39f",
  cream: "#f2e6d2",
  paper: "#ecdfc8",
  surface: "#fffaf2",
  line: "#cbbfae",
  sageInk: "#426b67",
};

export function readBrandTokens(): BrandTokens {
  const css = getComputedStyle(document.documentElement);
  const get = (name: string, fallback: string) => css.getPropertyValue(name).trim() || fallback;
  return {
    teal: get("--teal", FALLBACK.teal),
    charcoal: get("--charcoal", FALLBACK.charcoal),
    terracotta: get("--terracotta", FALLBACK.terracotta),
    sage: get("--sage", FALLBACK.sage),
    cream: get("--cream", FALLBACK.cream),
    paper: get("--paper", FALLBACK.paper),
    surface: get("--surface", FALLBACK.surface),
    line: get("--line", FALLBACK.line),
    sageInk: get("--sage-ink", FALLBACK.sageInk),
  };
}

/** `color-mix` isn't available to MapLibre, so tints are mixed here: `mix(a, b, 0.3)` is 30% b. */
export function mix(a: string, b: string, amount: number): string {
  const parse = (hex: string) => {
    const h = hex.replace("#", "");
    const full = h.length === 3 ? [...h].map((c) => c + c).join("") : h;
    return [0, 2, 4].map((i) => parseInt(full.slice(i, i + 2), 16));
  };
  const [x, y] = [parse(a), parse(b)];
  const out = x.map((v, i) => Math.round(v + (y[i] - v) * amount));
  return `#${out.map((v) => v.toString(16).padStart(2, "0")).join("")}`;
}

type PaintName = Parameters<MapLibreMap["setPaintProperty"]>[1];
type PaintValue = Parameters<MapLibreMap["setPaintProperty"]>[2];

const setPaint = (map: MapLibreMap, layer: string, prop: string, value: PaintValue) => {
  if (map.getLayer(layer)) map.setPaintProperty(layer, prop as PaintName, value);
};

export const BUILDINGS_LAYER = "haven-buildings-3d";

/**
 * Repaints positron in Haven's colours: warm cream land, sage-tinted water and parks, paper
 * roads with soft casings, charcoal labels. Flat buildings are replaced by 3D extrusions
 * whose height starts at zero so the arrival animation can raise them.
 */
export function applyBrand(map: MapLibreMap, t: BrandTokens) {
  const land = mix(t.cream, t.surface, 0.35);
  setPaint(map, "background", "background-color", land);
  setPaint(map, "landuse_residential", "fill-color", mix(t.cream, t.paper, 0.6));
  setPaint(map, "park", "fill-color", mix(land, t.sage, 0.28));
  setPaint(map, "landcover_wood", "fill-color", mix(land, t.sage, 0.38));
  setPaint(map, "water", "fill-color", mix(t.sage, t.surface, 0.45));
  setPaint(map, "waterway", "line-color", mix(t.sage, t.surface, 0.3));
  setPaint(map, "aeroway-area", "fill-color", mix(land, t.paper, 0.5));
  setPaint(map, "road_area_pier", "fill-color", land);
  setPaint(map, "road_pier", "line-color", land);

  const roadCasing = mix(t.line, t.paper, 0.35);
  for (const id of ["highway_major_casing", "highway_motorway_casing", "highway_motorway_bridge_casing", "tunnel_motorway_casing"]) {
    setPaint(map, id, "line-color", roadCasing);
  }
  for (const id of ["highway_major_inner", "highway_motorway_inner", "highway_motorway_bridge_inner", "tunnel_motorway_inner"]) {
    setPaint(map, id, "line-color", t.surface);
  }
  setPaint(map, "highway_minor", "line-color", mix(t.paper, t.surface, 0.3));
  setPaint(map, "highway_path", "line-color", mix(t.paper, t.line, 0.25));
  for (const id of ["highway_major_subtle", "highway_motorway_subtle"]) {
    setPaint(map, id, "line-color", mix(t.paper, t.line, 0.4));
  }
  for (const id of ["railway", "railway_transit", "railway_service"]) {
    setPaint(map, id, "line-color", mix(t.line, t.charcoal, 0.15));
  }
  for (const id of ["railway_dashline", "railway_transit_dashline", "railway_service_dashline"]) {
    setPaint(map, id, "line-color", t.surface);
  }
  for (const id of ["boundary_2", "boundary_3", "boundary_disputed"]) {
    setPaint(map, id, "line-color", mix(t.line, t.charcoal, 0.25));
  }

  for (const layer of map.getStyle().layers ?? []) {
    if (layer.type !== "symbol") continue;
    const isWater = layer.id.startsWith("water");
    setPaint(map, layer.id, "text-color", isWater ? t.sageInk : t.charcoal);
    setPaint(map, layer.id, "text-halo-color", land);
  }
  for (const id of ["highway-name-minor", "highway-name-major", "highway-name-path"]) {
    setPaint(map, id, "text-color", mix(t.charcoal, t.line, 0.35));
  }

  // 3D buildings, inserted under the first label layer so names stay readable.
  if (map.getLayer("building")) map.removeLayer("building");
  if (!map.getLayer(BUILDINGS_LAYER)) {
    const firstLabel = map.getStyle().layers?.find((l) => l.type === "symbol")?.id;
    map.addLayer(
      {
        id: BUILDINGS_LAYER,
        type: "fill-extrusion",
        source: "openmaptiles",
        "source-layer": "building",
        minzoom: 12,
        paint: {
          "fill-extrusion-color": [
            "interpolate",
            ["linear"],
            ["coalesce", ["get", "render_height"], 6],
            0,
            mix(t.paper, t.surface, 0.2),
            40,
            mix(t.paper, t.line, 0.55),
          ],
          "fill-extrusion-height": 0,
          "fill-extrusion-base": 0,
          "fill-extrusion-opacity": 0.92,
          "fill-extrusion-vertical-gradient": true,
        },
      },
      firstLabel,
    );
  }
}

/** Sets building heights to `k` × their real height (0 = flat, 1 = full). */
export function setBuildingRise(map: MapLibreMap, k: number) {
  if (!map.getLayer(BUILDINGS_LAYER)) return;
  map.setPaintProperty(BUILDINGS_LAYER, "fill-extrusion-height", [
    "*",
    ["coalesce", ["get", "render_height"], 6],
    k,
  ]);
  map.setPaintProperty(BUILDINGS_LAYER, "fill-extrusion-base", [
    "*",
    ["coalesce", ["get", "render_min_height"], 0],
    k,
  ]);
}
