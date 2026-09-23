import type { CityPageData, NeighbourhoodPageData } from "@/content/programmatic-seo/catalog";
import { absoluteUrl } from "@/content/seo-pages";
import { SITE_NAME } from "@/lib/site";

type JsonLd = Record<string, unknown>;

function breadcrumbItems(
  items: { name: string; path: string }[]
): JsonLd {
  return {
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    itemListElement: items.map((item, index) => ({
      "@type": "ListItem",
      position: index + 1,
      name: item.name,
      item: absoluteUrl(item.path),
    })),
  };
}

export function buildCityPageJsonLd(city: CityPageData): JsonLd {
  return breadcrumbItems([
    { name: "Início", path: "/" },
    { name: "Imóveis", path: "/imoveis" },
    { name: city.municipality, path: city.path },
  ]);
}

export function buildNeighbourhoodPageJsonLd(nbhd: NeighbourhoodPageData): JsonLd {
  return breadcrumbItems([
    { name: "Início", path: "/" },
    { name: "Imóveis", path: "/imoveis" },
    { name: nbhd.municipality, path: `/imoveis/${nbhd.citySlug}` },
    { name: nbhd.name, path: nbhd.path },
  ]);
}

export function buildHubPageJsonLd(): JsonLd {
  return breadcrumbItems([
    { name: "Início", path: "/" },
    { name: "Imóveis por cidade", path: "/imoveis" },
  ]);
}

export function buildNeighbourhoodAboutJsonLd(nbhd: NeighbourhoodPageData): JsonLd {
  return {
    "@context": "https://schema.org",
    "@type": "WebPage",
    name: `Imóveis em ${nbhd.name}, ${nbhd.municipality} | ${SITE_NAME}`,
    url: absoluteUrl(nbhd.path),
    about: {
      "@type": "Place",
      name: nbhd.name,
      containedInPlace: {
        "@type": "City",
        name: nbhd.municipality,
      },
    },
  };
}
