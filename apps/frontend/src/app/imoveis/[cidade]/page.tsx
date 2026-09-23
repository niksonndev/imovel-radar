import type { Metadata } from "next";
import { notFound } from "next/navigation";

import {
  CityLocationView,
  LocationJsonLdScript,
} from "@/components/programmatic/location-landing";
import { findCity } from "@/content/programmatic-seo/catalog";
import { cityMetadata } from "@/content/programmatic-seo/copy";
import { buildCityPageJsonLd } from "@/content/programmatic-seo/json-ld-location";
import { getLocationCatalogForBuild } from "@/lib/location-catalog-for-build";
import { SITE_URL } from "@/lib/site";

export const dynamic = "force-static";

type PageProps = {
  params: Promise<{ cidade: string }>;
};

export async function generateStaticParams() {
  const catalog = await getLocationCatalogForBuild();
  return catalog.cities.map((city) => ({ cidade: city.slug }));
}

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const { cidade } = await params;
  const catalog = await getLocationCatalogForBuild();
  const city = findCity(catalog, cidade);
  if (!city) return {};

  const copy = cityMetadata(city);
  const canonical = city.path;

  return {
    title: { absolute: copy.title },
    description: copy.description,
    keywords: [...copy.keywords],
    alternates: { canonical },
    openGraph: {
      title: copy.title,
      description: copy.description,
      url: `${SITE_URL.replace(/\/$/, "")}${canonical}`,
      locale: "pt_BR",
      type: "website",
    },
  };
}

export default async function CityImoveisPage({ params }: PageProps) {
  const { cidade } = await params;
  const catalog = await getLocationCatalogForBuild();
  const city = findCity(catalog, cidade);
  if (!city) notFound();

  const copy = cityMetadata(city);

  return (
    <>
      <LocationJsonLdScript data={buildCityPageJsonLd(city)} />
      <CityLocationView city={city} copy={copy} />
    </>
  );
}
