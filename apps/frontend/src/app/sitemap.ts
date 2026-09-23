import type { MetadataRoute } from "next";

import { SEO_PAGES } from "@/content/seo-pages";
import {
  getLocationCatalogForBuild,
  locationSitemapEntries,
} from "@/lib/location-catalog-for-build";
import { SITE_URL } from "@/lib/site";

export const dynamic = "force-static";

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const catalog = await getLocationCatalogForBuild();
  const locationEntries = locationSitemapEntries(catalog);
  const base = SITE_URL.replace(/\/$/, "");

  return [
    {
      url: SITE_URL,
      lastModified: new Date(catalog.collectedAt),
      changeFrequency: "weekly",
      priority: 1,
    },
    {
      url: `${base}/mercado`,
      lastModified: new Date(catalog.collectedAt),
      changeFrequency: "daily",
      priority: 0.9,
    },
    {
      url: `${base}/imoveis`,
      lastModified: new Date(catalog.collectedAt),
      changeFrequency: "weekly",
      priority: 0.85,
    },
    ...SEO_PAGES.map((page) => ({
      url: `${base}${page.path}`,
      lastModified: new Date(catalog.collectedAt),
      changeFrequency: "weekly" as const,
      priority: 0.8,
    })),
    ...locationEntries
      .filter((e) => e.path !== `${base}/imoveis`)
      .map((entry) => {
        const parts = new URL(entry.path).pathname.split("/").filter(Boolean);
        const isNeighbourhood =
          parts[0] === "imoveis" && parts.length >= 3;
        return {
          url: entry.path,
          lastModified: entry.lastModified,
          changeFrequency: "weekly" as const,
          priority: isNeighbourhood ? 0.75 : 0.8,
        };
      }),
  ];
}
