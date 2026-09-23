import { PRODUCT_FACTS } from "@/content/ai-seo/ai-content/product-facts";
import { BRAND_ENTITY } from "@/content/ai-seo/generative-engine-optimization/brand-entity";
import { SEO_PAGES, absoluteUrl } from "@/content/seo-pages";

type JsonLd = Record<string, unknown>;

function organizationSchema(): JsonLd {
  return {
    "@type": "Organization",
    "@id": `${PRODUCT_FACTS.url}/#organization`,
    name: PRODUCT_FACTS.name,
    url: PRODUCT_FACTS.url,
    description: PRODUCT_FACTS.description,
    sameAs: BRAND_ENTITY.sameAs,
    areaServed: {
      "@type": "City",
      name: PRODUCT_FACTS.coverage.city,
      containedInPlace: {
        "@type": "State",
        name: PRODUCT_FACTS.coverage.state,
      },
    },
  };
}

function softwareApplicationSchema(): JsonLd {
  return {
    "@type": "SoftwareApplication",
    "@id": `${PRODUCT_FACTS.url}/#app`,
    name: PRODUCT_FACTS.name,
    alternateName: [...BRAND_ENTITY.alternateNames],
    description: PRODUCT_FACTS.description,
    url: PRODUCT_FACTS.url,
    applicationCategory: BRAND_ENTITY.applicationCategory,
    operatingSystem: BRAND_ENTITY.operatingSystem,
    offers: [
      {
        "@type": "Offer",
        name: PRODUCT_FACTS.pricing.free.name,
        price: "0",
        priceCurrency: "BRL",
        description: PRODUCT_FACTS.pricing.free.features.join("; "),
      },
      {
        "@type": "Offer",
        name: PRODUCT_FACTS.pricing.pro.name,
        price: "19.90",
        priceCurrency: "BRL",
        description: PRODUCT_FACTS.pricing.pro.features.join("; "),
      },
    ],
    publisher: { "@id": `${PRODUCT_FACTS.url}/#organization` },
  };
}

function webSiteSchema(): JsonLd {
  return {
    "@type": "WebSite",
    "@id": `${PRODUCT_FACTS.url}/#website`,
    name: PRODUCT_FACTS.name,
    url: PRODUCT_FACTS.url,
    description: PRODUCT_FACTS.description,
    inLanguage: PRODUCT_FACTS.locale,
    publisher: { "@id": `${PRODUCT_FACTS.url}/#organization` },
  };
}

function faqPageSchema(): JsonLd {
  return {
    "@type": "FAQPage",
    "@id": `${PRODUCT_FACTS.url}/#faq`,
    mainEntity: PRODUCT_FACTS.faqs.map((item) => ({
      "@type": "Question",
      name: item.question,
      acceptedAnswer: {
        "@type": "Answer",
        text: item.answer,
      },
    })),
  };
}

function howToSchema(): JsonLd {
  return {
    "@type": "HowTo",
    "@id": `${PRODUCT_FACTS.url}/#howto`,
    name: `Como usar o ${PRODUCT_FACTS.name}`,
    description: PRODUCT_FACTS.description,
    step: PRODUCT_FACTS.howItWorks.map((text, index) => ({
      "@type": "HowToStep",
      position: index + 1,
      text,
    })),
  };
}

function breadcrumbListSchema(): JsonLd {
  const items = [
    { name: "Início", path: "/" },
    { name: "Imóveis por cidade", path: "/imoveis" },
    ...SEO_PAGES.map((page) => ({
      name: page.headline,
      path: page.path,
    })),
  ];

  return {
    "@type": "BreadcrumbList",
    itemListElement: items.map((item, index) => ({
      "@type": "ListItem",
      position: index + 1,
      name: item.name,
      item: absoluteUrl(item.path),
    })),
  };
}

/** Graph of AI SERP / rich-result schemas for the marketing site. */
export function buildSiteJsonLd(): JsonLd {
  return {
    "@context": "https://schema.org",
    "@graph": [
      organizationSchema(),
      softwareApplicationSchema(),
      webSiteSchema(),
      faqPageSchema(),
      howToSchema(),
      breadcrumbListSchema(),
    ],
  };
}
