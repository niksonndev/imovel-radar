import { foldName, polygonKey } from "@/content/neighbourhood-aliases";
import type { HeatMetric, NeighbourhoodStat } from "@/lib/market-stats";

export type LngLat = [number, number];

export type NeighbourhoodFeature = {
  type: "Feature";
  properties: {
    name: string;
    sample: number;
    medianPrice: number | null;
    medianM2: number | null;
    colored: 0 | 1;
    metric: number;
  };
  geometry: {
    type: string;
    coordinates: unknown;
  };
};

export type NeighbourhoodCollection = {
  type: "FeatureCollection";
  features: NeighbourhoodFeature[];
};

type BaseFeature = {
  type: "Feature";
  properties?: { name?: string };
  geometry: NeighbourhoodFeature["geometry"];
};

export function isFeatureCollection(value: unknown): value is { type: "FeatureCollection"; features: BaseFeature[] } {
  if (!value || typeof value !== "object") return false;
  const collection = value as { type?: string; features?: unknown };
  return collection.type === "FeatureCollection" && Array.isArray(collection.features);
}

function metricOf(stat: NeighbourhoodStat, metric: HeatMetric): number | null {
  if (!stat.ranked) return null;
  if (metric === "volume") return stat.sample;
  return stat.median_price_m2;
}

export function paintNeighbourhoods(
  base: { features: BaseFeature[] },
  neighbourhoods: NeighbourhoodStat[],
  metric: HeatMetric,
): { geojson: NeighbourhoodCollection; unmatched: NeighbourhoodStat[]; min: number; max: number } {
  const byKey = new Map<string, NeighbourhoodStat>();
  for (const stat of neighbourhoods) {
    const key = polygonKey(stat.name);
    const previous = byKey.get(key);
    if (!previous || stat.sample > previous.sample) byKey.set(key, stat);
  }

  const polygonKeys = new Set<string>();
  let min = Number.POSITIVE_INFINITY;
  let max = Number.NEGATIVE_INFINITY;

  const features: NeighbourhoodFeature[] = base.features.map((feature) => {
    const name = feature.properties?.name ?? "";
    const key = foldName(name);
    polygonKeys.add(key);
    const stat = byKey.get(key);
    const value = stat ? metricOf(stat, metric) : null;
    const colored = value != null && value > 0 ? 1 : 0;
    if (colored && value != null) {
      min = Math.min(min, value);
      max = Math.max(max, value);
    }
    return {
      type: "Feature",
      properties: {
        name,
        sample: stat?.sample ?? 0,
        medianPrice: stat?.median_price ?? null,
        medianM2: stat?.median_price_m2 ?? null,
        colored,
        metric: value ?? 0,
      },
      geometry: feature.geometry,
    };
  });

  const unmatched = neighbourhoods.filter((stat) => !polygonKeys.has(polygonKey(stat.name)));
  if (!Number.isFinite(min) || !Number.isFinite(max)) {
    min = 0;
    max = 0;
  }
  return {
    geojson: { type: "FeatureCollection", features },
    unmatched,
    min,
    max,
  };
}

export function boundsOf(collection: NeighbourhoodCollection): [LngLat, LngLat] | null {
  let minX = 180;
  let minY = 90;
  let maxX = -180;
  let maxY = -90;
  let found = false;

  const walk = (node: unknown): void => {
    if (!Array.isArray(node) || node.length === 0) return;
    if (typeof node[0] === "number" && typeof node[1] === "number") {
      const x = node[0];
      const y = node[1];
      minX = Math.min(minX, x);
      minY = Math.min(minY, y);
      maxX = Math.max(maxX, x);
      maxY = Math.max(maxY, y);
      found = true;
      return;
    }
    for (const child of node) walk(child);
  };

  for (const feature of collection.features) walk(feature.geometry.coordinates);
  if (!found) return null;
  return [
    [minX, minY],
    [maxX, maxY],
  ];
}

export function heatPaint(min: number, max: number) {
  const gray = "#2a2a2a";
  const low = "#1B4F72";
  const midColor = "#0077BC";
  const high = "#D97706";
  if (!(max > min)) {
    return {
      "fill-color": ["case", ["==", ["get", "colored"], 1], midColor, gray] as unknown,
      "fill-opacity": 0.82,
    };
  }
  const mid = min + (max - min) / 2;
  return {
    "fill-color": [
      "case",
      ["==", ["get", "colored"], 1],
      ["interpolate", ["linear"], ["get", "metric"], min, low, mid, midColor, max, high],
      gray,
    ] as unknown,
    "fill-opacity": 0.82,
  };
}
