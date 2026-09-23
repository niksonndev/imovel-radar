export type ListingKind = "aluguel" | "venda";
export type HeatMetric = "m2" | "volume";

export type CategoryStat = {
  category: string;
  sample: number;
  p25_price: number | null;
  median_price: number | null;
  p75_price: number | null;
  median_price_m2: number | null;
};

export type NeighbourhoodStat = {
  name: string;
  sample: number;
  median_price: number | null;
  median_price_m2: number | null;
  ranked: boolean;
};

export type RoomStat = {
  rooms: number;
  sample: number;
};

export type KindStats = {
  active_count: number;
  inactive_count: number;
  sample: number;
  p25_price: number | null;
  median_price: number | null;
  p75_price: number | null;
  median_price_m2: number | null;
  price_m2_sample: number;
  new_count: number;
  price_drop_count: number;
  median_rent_plus_condo: number | null;
  by_category: CategoryStat[];
  neighbourhoods: NeighbourhoodStat[];
  rooms: RoomStat[];
};

export type CityStats = {
  key: string;
  municipality: string;
  kinds: Record<ListingKind, KindStats>;
};

export type MarketSnapshot = {
  collected_at: string;
  min_sample: number;
  cities: CityStats[];
};

const CATEGORY_LABEL: Record<string, string> = {
  Apartamentos: "Apartamento",
  Casas: "Casa",
  "Aluguel de quartos": "Quarto",
};

export function marketStatsUrl(): string {
  const configured = process.env.NEXT_PUBLIC_MARKET_STATS_URL?.trim();
  if (configured) return configured;
  return "/market-stats.sample.json";
}

export function marketStatsIsSample(): boolean {
  return !process.env.NEXT_PUBLIC_MARKET_STATS_URL?.trim();
}

export function formatBRL(value: number | null | undefined): string {
  if (value == null) return "—";
  return value.toLocaleString("pt-BR", {
    style: "currency",
    currency: "BRL",
    maximumFractionDigits: 0,
  });
}

export function formatCount(value: number): string {
  return value.toLocaleString("pt-BR");
}

export function categoryLabel(category: string): string {
  return CATEGORY_LABEL[category] ?? category;
}

export function formatCollectedAt(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toLocaleString("pt-BR", {
    dateStyle: "short",
    timeStyle: "short",
    timeZone: "America/Maceio",
  });
}

export function isMarketSnapshot(value: unknown): value is MarketSnapshot {
  if (!value || typeof value !== "object") return false;
  const snapshot = value as MarketSnapshot;
  return typeof snapshot.collected_at === "string" && Array.isArray(snapshot.cities);
}
