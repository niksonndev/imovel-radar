import type { NeighbourhoodKindStats } from "@/content/programmatic-seo/catalog";
import { formatBRL, formatCount } from "@/lib/market-stats";

type Props = {
  title: string;
  data: NeighbourhoodKindStats;
};

export function StatsKindCard({ title, data }: Props) {
  const stat = data.stat;
  const ranked = stat?.ranked ?? false;

  return (
    <article
      className="rounded-xl border border-white/10 bg-white/5 p-5"
      aria-labelledby={`stats-${title}`}
    >
      <h3 id={`stats-${title}`} className="font-heading text-lg text-white">
        {title}
      </h3>
      {!stat ? (
        <p className="mt-2 text-sm text-white/50">Sem dados neste bairro.</p>
      ) : !ranked ? (
        <p className="mt-2 text-sm text-white/50">
          Amostra pequena ({formatCount(stat.sample)} anúncios) — mediana não exibida.
        </p>
      ) : (
        <dl className="mt-3 grid gap-2 text-sm">
          <div className="flex justify-between gap-4">
            <dt className="text-white/55">Mediana (preço pedido)</dt>
            <dd className="font-mono text-white">{formatBRL(stat.median_price)}</dd>
          </div>
          {stat.median_price_m2 != null && (
            <div className="flex justify-between gap-4">
              <dt className="text-white/55">Mediana R$/m²</dt>
              <dd className="font-mono text-white">
                {formatBRL(stat.median_price_m2)}
              </dd>
            </div>
          )}
          <div className="flex justify-between gap-4">
            <dt className="text-white/55">Amostra</dt>
            <dd className="font-mono text-white">{formatCount(stat.sample)}</dd>
          </div>
          {data.cityMedian != null && (
            <div className="flex justify-between gap-4 border-t border-white/10 pt-2">
              <dt className="text-white/55">Mediana na cidade</dt>
              <dd className="font-mono text-white/80">{formatBRL(data.cityMedian)}</dd>
            </div>
          )}
        </dl>
      )}
    </article>
  );
}
