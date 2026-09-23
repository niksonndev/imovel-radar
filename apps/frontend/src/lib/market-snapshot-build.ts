import { readFileSync } from "node:fs";
import { join } from "node:path";

import { isMarketSnapshot, type MarketSnapshot } from "@/lib/market-stats";

const SAMPLE_RELATIVE = join("public", "market-stats.sample.json");

function samplePath(): string {
  return join(process.cwd(), SAMPLE_RELATIVE);
}

function readSampleSnapshot(): MarketSnapshot {
  const raw = readFileSync(samplePath(), "utf8");
  const parsed: unknown = JSON.parse(raw);
  if (!isMarketSnapshot(parsed)) {
    throw new Error(`Invalid market snapshot at ${SAMPLE_RELATIVE}`);
  }
  return parsed;
}

/** Loads market snapshot at build time (SSG / sitemap). */
export async function loadMarketSnapshotForBuild(): Promise<MarketSnapshot> {
  const configured = process.env.NEXT_PUBLIC_MARKET_STATS_URL?.trim();
  if (!configured) {
    return readSampleSnapshot();
  }

  const url =
    configured.startsWith("http://") || configured.startsWith("https://")
      ? configured
      : new URL(configured, "http://localhost").toString();

  if (configured.startsWith("/")) {
    return readSampleSnapshot();
  }

  const response = await fetch(url, {
    headers: { Accept: "application/json" },
    next: { revalidate: 0 },
  });

  if (!response.ok) {
    throw new Error(
      `Failed to load market snapshot (${response.status}) from NEXT_PUBLIC_MARKET_STATS_URL`
    );
  }

  const parsed: unknown = await response.json();
  if (!isMarketSnapshot(parsed)) {
    throw new Error("NEXT_PUBLIC_MARKET_STATS_URL returned invalid market snapshot JSON");
  }

  if (parsed.cities.length === 0 && process.env.VERCEL_ENV === "production") {
    throw new Error("Market snapshot has no cities — cannot build location pages");
  }

  return parsed;
}
