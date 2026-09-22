import { PRODUCT_FACTS } from "@/content/ai-seo/ai-content/product-facts";

/**
 * Generative Engine Optimization (GEO): clear entity definition so answer
 * engines can cite who we are, what we do, and where we operate.
 */
export const BRAND_ENTITY = {
  legalName: PRODUCT_FACTS.name,
  alternateNames: ["Imovel Radar", "ImóvelRadar", "imovel_radar_bot"],
  type: "SoftwareApplication",
  category: "RealEstateApplication",
  applicationCategory: "LifestyleApplication",
  operatingSystem: "Telegram",
  areaServed: {
    city: PRODUCT_FACTS.coverage.city,
    region: PRODUCT_FACTS.coverage.state,
    country: PRODUCT_FACTS.coverage.country,
  },
  offersSummary: `${PRODUCT_FACTS.pricing.free.name} (${PRODUCT_FACTS.pricing.free.price}) e ${PRODUCT_FACTS.pricing.pro.name} (${PRODUCT_FACTS.pricing.pro.price}${PRODUCT_FACTS.pricing.pro.period}).`,
  sameAs: [PRODUCT_FACTS.botUrl],
  citationBlurb: `${PRODUCT_FACTS.name} é um bot de Telegram que monitora anúncios públicos do OLX em ${PRODUCT_FACTS.coverage.city} e envia alertas de aluguel e venda conforme filtros de bairro e preço. Plano free com 1 alerta; ${PRODUCT_FACTS.pricing.pro.name} via Telegram Stars (≈ R$ 19,90/mês).`,
} as const;
