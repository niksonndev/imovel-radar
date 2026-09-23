import type { Metadata } from "next";

import {
  LocationHubView,
  LocationJsonLdScript,
} from "@/components/programmatic/location-landing";
import { hubMetadata } from "@/content/programmatic-seo/copy";
import { buildHubPageJsonLd } from "@/content/programmatic-seo/json-ld-location";
import { getLocationCatalogForBuild } from "@/lib/location-catalog-for-build";
import { SITE_URL } from "@/lib/site";

export const dynamic = "force-static";

const copy = hubMetadata();

export const metadata: Metadata = {
  title: { absolute: copy.title },
  description: copy.description,
  keywords: [...copy.keywords],
  alternates: { canonical: "/imoveis" },
  openGraph: {
    title: copy.title,
    description: copy.description,
    url: `${SITE_URL.replace(/\/$/, "")}/imoveis`,
    locale: "pt_BR",
    type: "website",
  },
};

export default async function ImoveisHubPage() {
  const catalog = await getLocationCatalogForBuild();

  return (
    <>
      <LocationJsonLdScript data={buildHubPageJsonLd()} />
      <LocationHubView catalog={catalog} copy={copy} />
    </>
  );
}
