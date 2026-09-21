import type { MetadataRoute } from "next";

import { SEO_PAGES } from "@/content/seo-pages";
import { SITE_URL } from "@/lib/site";

export const dynamic = "force-static";

export default function sitemap(): MetadataRoute.Sitemap {
  const now = new Date();
  return [
    {
      url: SITE_URL,
      lastModified: now,
      changeFrequency: "weekly",
      priority: 1,
    },
    ...SEO_PAGES.map((page) => ({
      url: `${SITE_URL.replace(/\/$/, "")}${page.path}`,
      lastModified: now,
      changeFrequency: "weekly" as const,
      priority: 0.8,
    })),
  ];
}
