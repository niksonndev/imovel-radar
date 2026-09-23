import Link from "next/link";

import { TrackedCta } from "@/components/tracked-cta";
import { Footer } from "@/components/footer";
import { StatsKindCard } from "@/components/programmatic/stats-kind-card";
import type {
  CityPageData,
  LocationCatalog,
  NeighbourhoodPageData,
} from "@/content/programmatic-seo/catalog";
import type { LocationMetadataCopy } from "@/content/programmatic-seo/copy";
import { dataFreshnessLabel } from "@/content/programmatic-seo/copy";
import {
  HERO_CTA_HINT,
  SECTION_CTA_LABEL,
  TELEGRAM_BOT_URL,
} from "@/content/page-content";
import { formatBRL, formatCount } from "@/lib/market-stats";
import { SITE_NAME } from "@/lib/site";

function Breadcrumbs({ items }: { items: { label: string; href?: string }[] }) {
  return (
    <nav aria-label="Breadcrumb" className="flex flex-wrap items-center gap-2 text-sm">
      {items.map((item, i) => (
        <span key={`${item.label}-${i}`} className="flex items-center gap-2">
          {i > 0 && <span className="text-white/30">/</span>}
          {item.href ? (
            <Link
              href={item.href}
              className="font-mono text-xs uppercase tracking-wider text-primary-on-surface hover:underline"
            >
              {item.label}
            </Link>
          ) : (
            <span className="text-white/60">{item.label}</span>
          )}
        </span>
      ))}
    </nav>
  );
}

function FaqBlock({ faq }: { faq: LocationMetadataCopy["faq"] }) {
  return (
    <section className="mt-10 border-t border-white/10 pt-8" aria-labelledby="faq-heading">
      <h2 id="faq-heading" className="font-heading text-xl text-white">
        Perguntas frequentes
      </h2>
      <ul className="mt-4 flex flex-col gap-4">
        {faq.map((item) => (
          <li key={item.question}>
            <h3 className="text-sm font-medium text-white">{item.question}</h3>
            <p className="mt-1 text-sm leading-relaxed text-white/65">{item.answer}</p>
          </li>
        ))}
      </ul>
    </section>
  );
}

function CtaBlock({ ctaId }: { ctaId: string }) {
  return (
    <div className="flex flex-col items-start gap-2">
      <TrackedCta href={TELEGRAM_BOT_URL} ctaId={ctaId} className="btn-shine">
        {SECTION_CTA_LABEL}
      </TrackedCta>
      <p className="text-sm text-white/50">{HERO_CTA_HINT}</p>
    </div>
  );
}

function MercadoLink({ cityKey }: { cityKey?: string }) {
  const hasMap = cityKey === "maceio" || cityKey === "recife";
  return (
    <p className="text-sm text-white/55">
      {hasMap ? (
        <>
          Ver mapa e comparar bairros no{" "}
          <Link href="/mercado" className="text-primary-on-surface hover:underline">
            painel de mercado
          </Link>
          .
        </>
      ) : (
        <>
          Comparar cidades no{" "}
          <Link href="/mercado" className="text-primary-on-surface hover:underline">
            painel de mercado
          </Link>
          .
        </>
      )}
    </p>
  );
}

export function LocationHubView({
  catalog,
  copy,
}: {
  catalog: LocationCatalog;
  copy: LocationMetadataCopy;
}) {
  return (
    <div className="flex flex-1 flex-col">
      <main className="bg-surface">
        <section className="mx-auto flex max-w-3xl flex-col items-start gap-6 px-4 py-24 sm:py-32">
          <Breadcrumbs
            items={[
              { label: SITE_NAME, href: "/" },
              { label: "Imóveis" },
            ]}
          />
          <h1 className="font-heading text-4xl leading-tight tracking-tight text-white sm:text-5xl">
            {copy.headline}
          </h1>
          <p className="text-lg leading-relaxed text-white/70">{copy.intro}</p>
          <CtaBlock ctaId="pseo_hub_imoveis" />
          <ul className="mt-6 w-full divide-y divide-white/10 border-y border-white/10">
            {catalog.cities.map((city) => (
              <li key={city.slug} className="py-4">
                <Link
                  href={city.path}
                  className="group flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between"
                >
                  <span className="font-heading text-xl text-white group-hover:text-primary-on-surface">
                    {city.municipality}
                  </span>
                  <span className="text-sm text-white/55">
                    {formatCount(city.neighbourhoods.length)} bairros · venda{" "}
                    {formatBRL(city.kinds.venda.median_price)}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
          <p className="text-xs text-white/40">{dataFreshnessLabel(catalog.collectedAt)}</p>
          <FaqBlock faq={copy.faq} />
        </section>
      </main>
      <Footer />
    </div>
  );
}

export function CityLocationView({
  city,
  copy,
}: {
  city: CityPageData;
  copy: LocationMetadataCopy;
}) {
  return (
    <div className="flex flex-1 flex-col">
      <main className="bg-surface">
        <section className="mx-auto flex max-w-3xl flex-col items-start gap-6 px-4 py-24 sm:py-32">
          <Breadcrumbs
            items={[
              { label: SITE_NAME, href: "/" },
              { label: "Imóveis", href: "/imoveis" },
              { label: city.municipality },
            ]}
          />
          <h1 className="font-heading text-4xl leading-tight tracking-tight text-white sm:text-5xl">
            {copy.headline}
          </h1>
          <p className="text-lg leading-relaxed text-white/70">{copy.intro}</p>
          <CtaBlock ctaId={`pseo_city_${city.slug}`} />
          <MercadoLink cityKey={city.key} />
          <div className="grid w-full gap-4 sm:grid-cols-2">
            <StatsKindCard
              title="Venda (cidade)"
              data={{
                stat: {
                  name: city.municipality,
                  sample: city.kinds.venda.sample,
                  median_price: city.kinds.venda.median_price,
                  median_price_m2: city.kinds.venda.median_price_m2,
                  ranked: true,
                },
                cityMedian: city.kinds.venda.median_price,
                cityP75: city.kinds.venda.p75_price,
              }}
            />
            <StatsKindCard
              title="Aluguel (cidade)"
              data={{
                stat: {
                  name: city.municipality,
                  sample: city.kinds.aluguel.sample,
                  median_price: city.kinds.aluguel.median_price,
                  median_price_m2: city.kinds.aluguel.median_price_m2,
                  ranked: true,
                },
                cityMedian: city.kinds.aluguel.median_price,
                cityP75: city.kinds.aluguel.p75_price,
              }}
            />
          </div>
          <h2 className="mt-4 font-heading text-2xl text-white">Bairros</h2>
          <ul className="w-full divide-y divide-white/10 border-y border-white/10">
            {city.neighbourhoods.map((nbhd) => (
              <li key={nbhd.slug} className="py-3">
                <Link
                  href={nbhd.path}
                  className="flex flex-col gap-0.5 sm:flex-row sm:justify-between sm:gap-4"
                >
                  <span className="text-white hover:text-primary-on-surface">{nbhd.name}</span>
                  <span className="font-mono text-xs text-white/50">
                    venda {formatBRL(nbhd.venda.stat?.median_price ?? null)} · aluguel{" "}
                    {formatBRL(nbhd.aluguel.stat?.median_price ?? null)}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
          <section className="mt-4 rounded-xl border border-white/10 bg-white/5 p-5">
            <h2 className="font-heading text-lg text-white">Como montar seu alerta</h2>
            <p className="mt-2 text-sm leading-relaxed text-white/65">{copy.alertSection}</p>
          </section>
          <p className="text-xs text-white/40">{dataFreshnessLabel(city.collectedAt)}</p>
          <FaqBlock faq={copy.faq} />
        </section>
      </main>
      <Footer />
    </div>
  );
}

export function NeighbourhoodLocationView({
  nbhd,
  copy,
  cityKey,
}: {
  nbhd: NeighbourhoodPageData;
  copy: LocationMetadataCopy;
  cityKey: string;
}) {
  const ctaId = `pseo_nbhd_${nbhd.citySlug}_${nbhd.slug.replace(/-/g, "_")}`;

  return (
    <div className="flex flex-1 flex-col">
      <main className="bg-surface">
        <section className="mx-auto flex max-w-3xl flex-col items-start gap-6 px-4 py-24 sm:py-32">
          <Breadcrumbs
            items={[
              { label: SITE_NAME, href: "/" },
              { label: "Imóveis", href: "/imoveis" },
              { label: nbhd.municipality, href: `/imoveis/${nbhd.citySlug}` },
              { label: nbhd.name },
            ]}
          />
          <h1 className="font-heading text-4xl leading-tight tracking-tight text-white sm:text-5xl">
            {copy.headline}
          </h1>
          <p className="text-lg leading-relaxed text-white/70">{copy.intro}</p>
          <CtaBlock ctaId={ctaId} />
          <MercadoLink cityKey={cityKey} />
          <div className="grid w-full gap-4 sm:grid-cols-2">
            <StatsKindCard title="Venda" data={nbhd.venda} />
            <StatsKindCard title="Aluguel" data={nbhd.aluguel} />
          </div>
          <section className="rounded-xl border border-white/10 bg-white/5 p-5">
            <h2 className="font-heading text-lg text-white">Como montar seu alerta</h2>
            <p className="mt-2 text-sm leading-relaxed text-white/65">{copy.alertSection}</p>
          </section>
          <p className="text-xs text-white/40">{dataFreshnessLabel(nbhd.collectedAt)}</p>
          <FaqBlock faq={copy.faq} />
        </section>
      </main>
      <Footer />
    </div>
  );
}

export function LocationJsonLdScript({ data }: { data: Record<string, unknown> }) {
  return (
    <script
      type="application/ld+json"
      dangerouslySetInnerHTML={{ __html: JSON.stringify(data) }}
    />
  );
}
