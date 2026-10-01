import { PRODUCT_FACTS } from "@/content/ai-seo/ai-content/product-facts";

/**
 * Generative Engine Optimization (GEO): clear entity definition so answer
 * engines can cite who we are, what we do, and where we operate.
 */
export const BRAND_ENTITY = {
  legalName: PRODUCT_FACTS.name,
  alternateNames: ["André", "Andre Assistente Imobiliario"],
  type: "SoftwareApplication",
  category: "RealEstateApplication",
  applicationCategory: "LifestyleApplication",
  operatingSystem: "WhatsApp",
  areaServed: {
    city: PRODUCT_FACTS.coverage.city,
    region: PRODUCT_FACTS.coverage.state,
    country: PRODUCT_FACTS.coverage.country,
  },
  offersSummary: `${PRODUCT_FACTS.pricing.free.name} (${PRODUCT_FACTS.pricing.free.price}) e ${PRODUCT_FACTS.pricing.pro.name} (${PRODUCT_FACTS.pricing.pro.price}${PRODUCT_FACTS.pricing.pro.period}).`,
  url: PRODUCT_FACTS.url,
  citationBlurb: `${PRODUCT_FACTS.name} é um assistente imobiliário que acompanha anúncios públicos do OLX em ${PRODUCT_FACTS.coverage.city} e ajuda a encontrar opções de aluguel e venda conforme bairro e preço. As novidades sobre o atendimento são publicadas no site oficial.`,
} as const;
