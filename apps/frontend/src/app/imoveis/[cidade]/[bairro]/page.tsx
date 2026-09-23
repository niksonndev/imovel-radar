import type { Metadata } from "next";
import { notFound } from "next/navigation";

import {
  LocationJsonLdScript,
  NeighbourhoodLocationView,
} from "@/components/programmatic/location-landing";
import { allNeighbourhoodParams, findCity, findNeighbourhood } from "@/content/programmatic-seo/catalog";
import { neighbourhoodMetadata } from "@/content/programmatic-seo/copy";
import {
  buildNeighbourhoodAboutJsonLd,
  buildNeighbourhoodPageJsonLd,
} from "@/content/programmatic-seo/json-ld-location";
import { getLocationCatalogForBuild } from "@/lib/location-catalog-for-build";
import { SITE_URL } from "@/lib/site";

export const dynamic = "force-static";

type PageProps = {
  params: Promise<{ cidade: string; bairro: string }>;
};

export async function generateStaticParams() {
  const catalog = await getLocationCatalogForBuild();
  return allNeighbourhoodParams(catalog);
}

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const { cidade, bairro } = await params;
  const catalog = await getLocationCatalogForBuild();
  const nbhd = findNeighbourhood(catalog, cidade, bairro);
  if (!nbhd) return {};

  const copy = neighbourhoodMetadata(nbhd);

  return {
    title: { absolute: copy.title },
    description: copy.description,
    keywords: [...copy.keywords],
    alternates: { canonical: nbhd.path },
    openGraph: {
      title: copy.title,
      description: copy.description,
      url: `${SITE_URL.replace(/\/$/, "")}${nbhd.path}`,
      locale: "pt_BR",
      type: "website",
    },
  };
}

export default async function NeighbourhoodImoveisPage({ params }: PageProps) {
  const { cidade, bairro } = await params;
  const catalog = await getLocationCatalogForBuild();
  const city = findCity(catalog, cidade);
  const nbhd = findNeighbourhood(catalog, cidade, bairro);
  if (!city || !nbhd) notFound();

  const copy = neighbourhoodMetadata(nbhd);

  return (
    <>
      <LocationJsonLdScript data={buildNeighbourhoodPageJsonLd(nbhd)} />
      <LocationJsonLdScript data={buildNeighbourhoodAboutJsonLd(nbhd)} />
      <NeighbourhoodLocationView nbhd={nbhd} copy={copy} cityKey={city.key} />
    </>
  );
}
