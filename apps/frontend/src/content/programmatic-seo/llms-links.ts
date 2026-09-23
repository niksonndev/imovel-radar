import { readFileSync } from "node:fs";
import { join } from "node:path";

import { buildLocationCatalog } from "@/content/programmatic-seo/catalog";
import { isMarketSnapshot } from "@/lib/market-stats";
import { absoluteUrl } from "@/content/seo-pages";

const TOP_NEIGHBOURHOODS = 8;

function readSnapshotForLlms(): ReturnType<typeof buildLocationCatalog> | null {
  try {
    const raw = readFileSync(
      join(process.cwd(), "public", "market-stats.sample.json"),
      "utf8"
    );
    const parsed: unknown = JSON.parse(raw);
    if (!isMarketSnapshot(parsed)) return null;
    return buildLocationCatalog(parsed);
  } catch {
    return null;
  }
}

/** Curated links for llms.txt (build-time, from bundled sample or same file CI uses locally). */
export function buildProgrammaticLlmsSection(): string {
  const catalog = readSnapshotForLlms();
  const lines = [
    `- [Imóveis por cidade](${absoluteUrl("/imoveis")}): preços pedidos no OLX por cidade e bairro (dados agregados)`,
  ];

  if (!catalog) return lines.join("\n");

  const ranked = catalog.cities.flatMap((city) =>
    city.neighbourhoods.map((nbhd) => ({
      label: `${nbhd.name}, ${city.municipality}`,
      path: nbhd.path,
      topSample: nbhd.topSample,
    }))
  );

  ranked.sort((a, b) => b.topSample - a.topSample);

  for (const item of ranked.slice(0, TOP_NEIGHBOURHOODS)) {
    lines.push(
      `- [${item.label}](${absoluteUrl(item.path)}): medianas de aluguel e venda no bairro`
    );
  }

  return lines.join("\n");
}
