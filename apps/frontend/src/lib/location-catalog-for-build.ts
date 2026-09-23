import {
  buildLocationCatalog,
  type LocationCatalog,
} from "@/content/programmatic-seo/catalog";
import { loadMarketSnapshotForBuild } from "@/lib/market-snapshot-build";
import { SITE_URL } from "@/lib/site";

let catalogPromise: Promise<LocationCatalog> | null = null;

/** Single cached catalog per build (snapshot → location pages). */
export async function getLocationCatalogForBuild(): Promise<LocationCatalog> {
  if (!catalogPromise) {
    catalogPromise = loadMarketSnapshotForBuild().then(buildLocationCatalog);
  }
  return catalogPromise;
}

export type LocationSitemapEntry = {
  path: string;
  lastModified: Date;
};

export function locationSitemapEntries(catalog: LocationCatalog): LocationSitemapEntry[] {
  const lastModified = new Date(catalog.collectedAt);
  const base = SITE_URL.replace(/\/$/, "");
  const entries: LocationSitemapEntry[] = [
    { path: `${base}/imoveis`, lastModified },
  ];

  for (const city of catalog.cities) {
    entries.push({ path: `${base}${city.path}`, lastModified });
    for (const nbhd of city.neighbourhoods) {
      entries.push({ path: `${base}${nbhd.path}`, lastModified });
    }
  }

  return entries;
}
