"use client";

import { boundsOf, heatPaint, type NeighbourhoodCollection } from "@/lib/market-geo";
import { formatBRL, formatCount, type HeatMetric } from "@/lib/market-stats";
import { getVersion, setWorkerUrl, type FillLayerSpecification } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { useEffect, useMemo, useRef, useState } from "react";
import Map, { Layer, Source, type MapLayerMouseEvent, type MapRef } from "react-map-gl/maplibre";

// Vercel runs bare `next build` and skips package `prebuild`, so `/maplibre/*` 404s
// in production. Load the worker from the CDN matching the installed package version.
setWorkerUrl(`https://cdn.jsdelivr.net/npm/maplibre-gl@${getVersion()}/dist/maplibre-gl-worker.mjs`);

const MAP_STYLE = "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json";

type Hover = {
  x: number;
  y: number;
  name: string;
  sample: number;
  medianPrice: number | null;
  medianM2: number | null;
  colored: number;
};

function readHover(event: MapLayerMouseEvent): Hover | null {
  const feature = event.features?.[0];
  if (!feature?.properties) return null;
  const props = feature.properties;
  const name = typeof props.name === "string" ? props.name : "";
  if (!name) return null;
  return {
    x: event.point.x,
    y: event.point.y,
    name,
    sample: Number(props.sample) || 0,
    medianPrice: props.medianPrice == null ? null : Number(props.medianPrice),
    medianM2: props.medianM2 == null ? null : Number(props.medianM2),
    colored: Number(props.colored) || 0,
  };
}

export function MarketMap({
  geojson,
  metric,
  min,
  max,
}: {
  geojson: NeighbourhoodCollection;
  metric: HeatMetric;
  min: number;
  max: number;
}) {
  const mapRef = useRef<MapRef>(null);
  const [hover, setHover] = useState<Hover | null>(null);
  const bounds = useMemo(() => boundsOf(geojson), [geojson]);
  const paint = useMemo(() => heatPaint(min, max) as FillLayerSpecification["paint"], [min, max]);

  const boundsKey = bounds ? bounds.flat().join(",") : "";

  useEffect(() => {
    if (!bounds) return;
    mapRef.current?.fitBounds(bounds, { padding: 28, duration: 500 });
  }, [bounds, boundsKey]);

  const legendMin = metric === "m2" ? `${formatCount(Math.round(min))} R$/m²` : formatCount(Math.round(min));
  const legendMax = metric === "m2" ? `${formatCount(Math.round(max))} R$/m²` : formatCount(Math.round(max));

  return (
    <div className="relative h-[min(70vh,560px)] min-h-80 overflow-hidden rounded-2xl border border-white/10">
      <Map
        ref={mapRef}
        initialViewState={{ longitude: -35.2, latitude: -8.8, zoom: 6 }}
        mapStyle={MAP_STYLE}
        style={{ width: "100%", height: "100%" }}
        attributionControl={{ compact: true }}
        interactiveLayerIds={["bairros-fill"]}
        onLoad={() => {
          if (!bounds) return;
          mapRef.current?.fitBounds(bounds, { padding: 28, duration: 0 });
        }}
        onMouseMove={(event) => setHover(readHover(event))}
        onMouseLeave={() => setHover(null)}
        cursor="pointer"
      >
        <Source id="bairros" type="geojson" data={geojson}>
          <Layer id="bairros-fill" type="fill" paint={paint} />
          <Layer
            id="bairros-line"
            type="line"
            paint={{ "line-color": "rgba(255,255,255,0.45)", "line-width": 1 }}
          />
        </Source>
      </Map>

      <div className="pointer-events-none absolute bottom-3 left-3 rounded-lg bg-black/70 px-3 py-2 text-[11px] text-white/80">
        <p className="mb-1 font-mono uppercase tracking-wider">
          {metric === "m2" ? "R$/m²" : "Anúncios"}
        </p>
        <div className="flex items-center gap-2">
          <span>{max > min ? legendMin : "—"}</span>
          <span
            aria-hidden="true"
            className="h-2 w-24 rounded-full"
            style={{ background: "linear-gradient(90deg, #1B4F72, #0077BC, #D97706)" }}
          />
          <span>{max > min ? legendMax : "—"}</span>
        </div>
        <p className="mt-1 text-white/50">Cinza: amostra pequena ou sem m²</p>
      </div>

      {hover ? (
        <div
          className="pointer-events-none absolute z-10 max-w-55 rounded-lg border border-white/15 bg-[#161616]/95 px-3 py-2 text-xs shadow-lg"
          style={{ left: Math.min(hover.x + 12, 280), top: hover.y + 12 }}
        >
          <p className="font-medium text-white">{hover.name}</p>
          {hover.sample === 0 ? (
            <p className="text-white/60">Sem anúncios nesta conta</p>
          ) : (
            <>
              <p className="text-white/80">{formatBRL(hover.medianPrice)} mediana</p>
              <p className="text-white/80">
                {hover.medianM2 == null ? "—" : `${formatCount(hover.medianM2)} R$/m²`}
              </p>
              <p className="text-white/60">{formatCount(hover.sample)} anúncios</p>
              {hover.colored === 0 ? <p className="text-white/45">Fora da escala</p> : null}
            </>
          )}
        </div>
      ) : null}
    </div>
  );
}
