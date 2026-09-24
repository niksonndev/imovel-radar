"use client";

import { HorizontalBars, type BarItem } from "@/components/market/horizontal-bars";
import { StatFigure } from "@/components/market/stat-figure";
import { TrackedCta } from "@/components/tracked-cta";
import { TELEGRAM_BOT_URL } from "@/content/page-content";
import {
  isFeatureCollection,
  paintNeighbourhoods,
  type NeighbourhoodCollection,
} from "@/lib/market-geo";
import {
  categoryLabel,
  formatBRL,
  formatCollectedAt,
  formatCount,
  isMarketSnapshot,
  marketStatsIsSample,
  marketStatsUrl,
  type CityStats,
  type HeatMetric,
  type KindStats,
  type ListingKind,
  type MarketSnapshot,
} from "@/lib/market-stats";
import { cn } from "@/lib/utils";
import dynamic from "next/dynamic";
import { useEffect, useMemo, useState } from "react";

const MarketMapLazy = dynamic(
  () => import("@/components/market/market-map").then((mod) => mod.MarketMap),
  {
    ssr: false,
    loading: () => (
      <div className="h-[min(70vh,560px)] min-h-80 animate-pulse rounded-2xl bg-white/5" />
    ),
  },
);

function Segmented<T extends string>({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: T;
  options: { value: T; label: string }[];
  onChange: (value: T) => void;
}) {
  return (
    <div role="group" aria-label={label} className="flex flex-wrap gap-2">
      {options.map((option) => {
        const selected = option.value === value;
        return (
          <button
            key={option.value}
            type="button"
            aria-pressed={selected}
            onClick={() => onChange(option.value)}
            className={cn(
              "rounded-lg border px-3 py-1.5 text-sm transition-colors",
              selected
                ? "border-primary bg-primary text-primary-foreground"
                : "border-white/15 bg-white/5 text-white/70 hover:bg-white/10 hover:text-white",
            )}
          >
            {option.label}
          </button>
        );
      })}
    </div>
  );
}

function neighbourhoodBars(kind: KindStats, metric: HeatMetric): BarItem[] {
  return kind.neighbourhoods
    .filter((item) => item.ranked)
    .map((item) => ({
      key: item.name,
      label: item.name,
      value: metric === "volume" ? item.sample : (item.median_price_m2 ?? 0),
      display: metric === "volume" ? formatCount(item.sample) : formatBRL(item.median_price_m2),
    }))
    .filter((item) => item.value > 0)
    .sort((a, b) => b.value - a.value)
    .slice(0, 10);
}

export function MarketDashboard() {
  const illustrative = marketStatsIsSample();
  const [snapshot, setSnapshot] = useState<MarketSnapshot | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [cityKey, setCityKey] = useState("maceio");
  const [kind, setKind] = useState<ListingKind>("aluguel");
  const [metric, setMetric] = useState<HeatMetric>("m2");
  const [boundaries, setBoundaries] = useState<Record<string, NeighbourhoodCollection | "error">>({});

  useEffect(() => {
    const controller = new AbortController();
    fetch(marketStatsUrl(), { signal: controller.signal })
      .then(async (response) => {
        if (!response.ok) throw new Error(String(response.status));
        return response.json() as Promise<unknown>;
      })
      .then((payload) => {
        if (!isMarketSnapshot(payload)) throw new Error("formato");
        setSnapshot(payload);
        if (payload.cities[0]) setCityKey(payload.cities[0].key);
      })
      .catch((reason: unknown) => {
        if (reason instanceof DOMException && reason.name === "AbortError") return;
        setError("Não foi possível carregar as estatísticas.");
      });
    return () => controller.abort();
  }, []);

  const city: CityStats | undefined = snapshot?.cities.find((item) => item.key === cityKey);
  const stats = city?.kinds[kind];

  useEffect(() => {
    if (!city || boundaries[city.key]) return;
    const controller = new AbortController();
    fetch(`/geo/${city.key}-bairros.geojson`, { signal: controller.signal })
      .then(async (response) => {
        if (!response.ok) throw new Error(String(response.status));
        return response.json() as Promise<unknown>;
      })
      .then((payload) => {
        if (!isFeatureCollection(payload)) throw new Error("geo");
        setBoundaries((current) => ({
          ...current,
          [city.key]: {
            type: "FeatureCollection",
            features: payload.features.map((feature) => ({
              type: "Feature" as const,
              properties: {
                name: feature.properties?.name ?? "",
                sample: 0,
                medianPrice: null,
                medianM2: null,
                colored: 0 as const,
                metric: 0,
              },
              geometry: feature.geometry,
            })),
          },
        }));
      })
      .catch((reason: unknown) => {
        if (reason instanceof DOMException && reason.name === "AbortError") return;
        setBoundaries((current) => ({ ...current, [city.key]: "error" }));
      });
    return () => controller.abort();
  }, [city, boundaries]);

  const painted = useMemo(() => {
    if (!stats || !city) return null;
    const base = boundaries[city.key];
    if (!base || base === "error") return null;
    return paintNeighbourhoods(base, stats.neighbourhoods, metric);
  }, [stats, city, boundaries, metric]);

  if (error) {
    return <p className="mx-auto max-w-6xl px-4 py-16 text-white/70">{error}</p>;
  }
  if (!snapshot || !city || !stats) {
    return (
      <p className="mx-auto max-w-6xl px-4 py-16 text-white/60" role="status">
        Carregando o mercado…
      </p>
    );
  }

  const categoryItems: BarItem[] = stats.by_category.map((item) => ({
    key: item.category,
    label: categoryLabel(item.category),
    value: item.sample,
    display: `${formatCount(item.sample)} · ${formatBRL(item.median_price)}`,
  }));
  const roomItems: BarItem[] = stats.rooms.map((item) => ({
    key: String(item.rooms),
    label: item.rooms === 1 ? "1 quarto" : `${item.rooms} quartos`,
    value: item.sample,
    display: formatCount(item.sample),
  }));
  const rankedRows = [...stats.neighbourhoods].sort((a, b) => {
    if (a.ranked !== b.ranked) return a.ranked ? -1 : 1;
    return b.sample - a.sample;
  });

  return (
    <div className="mx-auto flex w-full max-w-6xl flex-col gap-10 px-4 py-10">
      {illustrative ? (
        <p className="rounded-xl border border-warning/40 bg-warning/10 px-4 py-3 text-sm text-white/80">
          Números de exemplo. O painel passa a usar a coleta do dia quando{" "}
          <span className="font-mono">NEXT_PUBLIC_MARKET_STATS_URL</span> aponta para o snapshot.
        </p>
      ) : null}

      <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div className="flex flex-col gap-3">
          <Segmented
            label="Cidade"
            value={cityKey}
            onChange={setCityKey}
            options={snapshot.cities.map((item) => ({
              value: item.key,
              label: item.municipality,
            }))}
          />
          <Segmented
            label="Tipo de anúncio"
            value={kind}
            onChange={setKind}
            options={[
              { value: "aluguel", label: "Aluguel" },
              { value: "venda", label: "Venda" },
            ]}
          />
        </div>
        <p className="text-sm text-white/50">
          Coleta de {formatCollectedAt(snapshot.collected_at)} · preço pedido no OLX · amostra
          mínima de {snapshot.min_sample} anúncios por bairro
        </p>
      </div>

      <section aria-label="Resumo" className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <article className="rounded-2xl border border-white/10 bg-white/5 p-4">
          <p className="text-sm text-white/60">Mediana</p>
          <StatFigure key={`${cityKey}-${kind}-median`} value={stats.median_price} currency />
          <p className="mt-1 text-xs text-white/45">
            {formatBRL(stats.p25_price)} – {formatBRL(stats.p75_price)}
          </p>
        </article>
        <article className="rounded-2xl border border-white/10 bg-white/5 p-4">
          <p className="text-sm text-white/60">Mediana por m²</p>
          <StatFigure key={`${cityKey}-${kind}-m2`} value={stats.median_price_m2} currency />
          <p className="mt-1 text-xs text-white/45">
            {formatCount(stats.price_m2_sample)} anúncios com área
          </p>
        </article>
        {kind === "aluguel" ? (
          <article className="rounded-2xl border border-white/10 bg-white/5 p-4">
            <p className="text-sm text-white/60">Aluguel + condomínio</p>
            <StatFigure
              key={`${cityKey}-${kind}-condo`}
              value={stats.median_rent_plus_condo}
              currency
            />
            <p className="mt-1 text-xs text-white/45">Quando o anúncio informa condomínio</p>
          </article>
        ) : null}
        <article className="rounded-2xl border border-white/10 bg-white/5 p-4">
          <p className="text-sm text-white/60">Anúncios ativos</p>
          <StatFigure key={`${cityKey}-${kind}-active`} value={stats.active_count} />
          <p className="mt-1 text-xs text-white/45">
            {formatCount(stats.sample)} entram na mediana · {formatCount(stats.inactive_count)}{" "}
            inativos
          </p>
        </article>
        <article className="rounded-2xl border border-white/10 bg-white/5 p-4">
          <p className="text-sm text-white/60">Novos em 36h</p>
          <StatFigure key={`${cityKey}-${kind}-new`} value={stats.new_count} />
        </article>
        <article className="rounded-2xl border border-white/10 bg-white/5 p-4">
          <p className="text-sm text-white/60">Com queda de preço</p>
          <StatFigure key={`${cityKey}-${kind}-drop`} value={stats.price_drop_count} />
          <p className="mt-1 text-xs text-white/45">Preço anterior do próprio anúncio</p>
        </article>
      </section>

      <section className="grid gap-6 lg:grid-cols-[minmax(0,1.4fr)_minmax(0,0.8fr)]">
        <div className="flex flex-col gap-3">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h2 className="font-heading text-xl text-white">Mapa de calor</h2>
            <Segmented
              label="Métrica do mapa"
              value={metric}
              onChange={setMetric}
              options={[
                { value: "m2", label: "R$/m²" },
                { value: "volume", label: "Volume" },
              ]}
            />
          </div>
          {boundaries[city.key] === "error" ? (
            <p className="text-sm text-white/60">Contorno dos bairros indisponível.</p>
          ) : painted ? (
            <MarketMapLazy
              geojson={painted.geojson}
              metric={metric}
              min={painted.min}
              max={painted.max}
            />
          ) : (
            <div className="h-[min(70vh,560px)] min-h-80 animate-pulse rounded-2xl bg-white/5" />
          )}
          <p className="text-xs leading-relaxed text-white/40">
            Contornos: Prefeitura do Recife (ODbL) e bairros do Censo IBGE 2022 publicados por
            Alagoas em Dados (CC BY). Mapa base © CARTO © OpenStreetMap.
          </p>
        </div>

        <div className="flex max-h-140 flex-col gap-3 overflow-auto rounded-2xl border border-white/10 bg-white/5 p-4">
          <h2 className="font-heading text-xl text-white">Bairros</h2>
          <table className="w-full text-left text-sm">
            <caption className="sr-only">
              Mediana e volume por bairro em {city.municipality}
            </caption>
            <thead className="text-xs uppercase tracking-wider text-white/45">
              <tr>
                <th className="py-2 font-medium">Bairro</th>
                <th className="py-2 text-right font-medium">N</th>
                <th className="py-2 text-right font-medium">Mediana</th>
                <th className="py-2 text-right font-medium">R$/m²</th>
              </tr>
            </thead>
            <tbody>
              {rankedRows.map((item) => (
                <tr key={item.name} className="border-t border-white/10">
                  <th className="py-2 pr-2 font-normal text-white/90" scope="row">
                    {item.name}
                    {item.ranked ? null : (
                      <span className="ml-2 text-[10px] uppercase tracking-wider text-white/40">
                        amostra
                      </span>
                    )}
                  </th>
                  <td className="py-2 text-right font-mono text-white/70">{formatCount(item.sample)}</td>
                  <td className="py-2 text-right text-white/80">{formatBRL(item.median_price)}</td>
                  <td className="py-2 text-right text-white/80">
                    {item.median_price_m2 == null ? "—" : formatCount(item.median_price_m2)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {painted && painted.unmatched.length > 0 ? (
            <p className="text-xs text-white/45">
              Sem contorno no mapa: {painted.unmatched.map((item) => item.name).join(", ")}.
            </p>
          ) : null}
        </div>
      </section>

      <section className="grid gap-8 lg:grid-cols-2">
        <div className="flex flex-col gap-3">
          <h2 className="font-heading text-xl text-white">
            {metric === "m2" ? "Maior R$/m²" : "Mais anúncios"}
          </h2>
          <HorizontalBars
            label="Ranking de bairros"
            items={neighbourhoodBars(stats, metric)}
            color={metric === "m2" ? "#D97706" : "#0077BC"}
          />
        </div>
        <div className="flex flex-col gap-6">
          <div className="flex flex-col gap-3">
            <h2 className="font-heading text-xl text-white">Por tipo</h2>
            <HorizontalBars label="Anúncios por categoria" items={categoryItems} color="#009866" />
          </div>
          <div className="flex flex-col gap-3">
            <h2 className="font-heading text-xl text-white">Quartos</h2>
            <HorizontalBars label="Anúncios por quantidade de quartos" items={roomItems} />
          </div>
        </div>
      </section>

      <section className="flex flex-col items-start gap-3 rounded-2xl border border-white/10 bg-white/5 p-6">
        <h2 className="font-heading text-2xl text-white">Quer o anúncio, não só a mediana?</h2>
        <p className="max-w-xl text-sm leading-relaxed text-white/65">
          Estes números são preços pedidos em anúncios ativos. O bot avisa no Telegram quando entra
          um imóvel no bairro e na faixa que você escolher.
        </p>
        <TrackedCta href={TELEGRAM_BOT_URL} ctaId="mercado" className="btn-shine">
          Começar grátis no Telegram
        </TrackedCta>
      </section>
    </div>
  );
}
