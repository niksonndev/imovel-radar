import type {
  KindStats,
  ListingKind,
  MarketSnapshot,
  NeighbourhoodStat,
} from "@/lib/market-stats";

import { matchesNeighbourhoodSlug, neighbourhoodSlugFromName, slugifyLocation } from "./slugs";

export type NeighbourhoodKindStats = {
  stat: NeighbourhoodStat | null;
  cityMedian: number | null;
  cityP75: number | null;
};

export type NeighbourhoodPageData = {
  slug: string;
  name: string;
  path: string;
  citySlug: string;
  municipality: string;
  collectedAt: string;
  aluguel: NeighbourhoodKindStats;
  venda: NeighbourhoodKindStats;
  /** Max sample across kinds (for sorting). */
  topSample: number;
};

export type CityPageData = {
  slug: string;
  key: string;
  municipality: string;
  path: string;
  collectedAt: string;
  kinds: Record<ListingKind, KindStats>;
  neighbourhoods: NeighbourhoodPageData[];
};

export type LocationCatalog = {
  collectedAt: string;
  minSample: number;
  cities: CityPageData[];
};

function findNeighbourhoodStat(
  kindStats: KindStats,
  name: string
): NeighbourhoodStat | null {
  return kindStats.neighbourhoods.find((n) => n.name === name) ?? null;
}

function rankedNeighbourhoodNames(
  aluguel: KindStats,
  venda: KindStats
): string[] {
  const names = new Set<string>();
  for (const n of aluguel.neighbourhoods) {
    if (n.ranked) names.add(n.name);
  }
  for (const n of venda.neighbourhoods) {
    if (n.ranked) names.add(n.name);
  }
  return [...names].sort((a, b) => a.localeCompare(b, "pt-BR"));
}

function buildNeighbourhoodPage(
  citySlug: string,
  municipality: string,
  collectedAt: string,
  name: string,
  aluguelKind: KindStats,
  vendaKind: KindStats
): NeighbourhoodPageData {
  const slug = neighbourhoodSlugFromName(name);
  const aluguelStat = findNeighbourhoodStat(aluguelKind, name);
  const vendaStat = findNeighbourhoodStat(vendaKind, name);
  const topSample = Math.max(aluguelStat?.sample ?? 0, vendaStat?.sample ?? 0);

  return {
    slug,
    name,
    path: `/imoveis/${citySlug}/${slug}`,
    citySlug,
    municipality,
    collectedAt,
    topSample,
    aluguel: {
      stat: aluguelStat,
      cityMedian: aluguelKind.median_price,
      cityP75: aluguelKind.p75_price,
    },
    venda: {
      stat: vendaStat,
      cityMedian: vendaKind.median_price,
      cityP75: vendaKind.p75_price,
    },
  };
}

export function buildLocationCatalog(snapshot: MarketSnapshot): LocationCatalog {
  const cities: CityPageData[] = snapshot.cities.map((city) => {
    const citySlug = slugifyLocation(city.key);
    const aluguel = city.kinds.aluguel;
    const venda = city.kinds.venda;
    const names = rankedNeighbourhoodNames(aluguel, venda);
    const neighbourhoods = names.map((name) =>
      buildNeighbourhoodPage(
        citySlug,
        city.municipality,
        snapshot.collected_at,
        name,
        aluguel,
        venda
      )
    );

    neighbourhoods.sort((a, b) => b.topSample - a.topSample);

    return {
      slug: citySlug,
      key: city.key,
      municipality: city.municipality,
      path: `/imoveis/${citySlug}`,
      collectedAt: snapshot.collected_at,
      kinds: city.kinds,
      neighbourhoods,
    };
  });

  return {
    collectedAt: snapshot.collected_at,
    minSample: snapshot.min_sample,
    cities,
  };
}

export function findCity(
  catalog: LocationCatalog,
  citySlug: string
): CityPageData | undefined {
  return catalog.cities.find((c) => c.slug === citySlug);
}

export function findNeighbourhood(
  catalog: LocationCatalog,
  citySlug: string,
  neighbourhoodSlug: string
): NeighbourhoodPageData | undefined {
  const city = findCity(catalog, citySlug);
  if (!city) return undefined;
  return city.neighbourhoods.find((n) =>
    matchesNeighbourhoodSlug(n.name, neighbourhoodSlug)
  );
}

export function allNeighbourhoodParams(
  catalog: LocationCatalog
): { cidade: string; bairro: string }[] {
  const params: { cidade: string; bairro: string }[] = [];
  for (const city of catalog.cities) {
    for (const nbhd of city.neighbourhoods) {
      params.push({ cidade: city.slug, bairro: nbhd.slug });
    }
  }
  return params;
}
