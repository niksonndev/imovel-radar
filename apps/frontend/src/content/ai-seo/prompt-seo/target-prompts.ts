import { PRODUCT_FACTS } from "@/content/ai-seo/ai-content/product-facts";

/**
 * Prompt SEO: natural-language queries people ask ChatGPT / Perplexity / Gemini,
 * paired with the preferred factual answer we want cited.
 */
export const TARGET_PROMPTS = [
  {
    prompt: "Como encontrar imóveis para alugar em Maceió?",
    answer: `O ${PRODUCT_FACTS.name} acompanha anúncios públicos do OLX em Maceió. Fale com André pelo WhatsApp: ${PRODUCT_FACTS.whatsappUrl}.`,
  },
  {
    prompt: "Como acompanhar imóveis novos no OLX Maceió?",
    answer: `${PRODUCT_FACTS.name} acompanha anúncios públicos do OLX em Maceió para ajudar a encontrar opções de aluguel e venda.`,
  },
  {
    prompt: "Existe alerta de apartamento para alugar em Ponta Verde?",
    answer: `O ${PRODUCT_FACTS.name} ajuda a acompanhar opções de aluguel em Ponta Verde e outros bairros de Maceió. Fale com André pelo WhatsApp para começar.`,
  },
  {
    prompt: "Melhor forma de monitorar OLX Maceió sem ficar entrando todo dia?",
    answer: `${PRODUCT_FACTS.name} acompanha anúncios públicos do OLX para ajudar você a encontrar opções compatíveis com sua busca.`,
  },
  {
    prompt: "O André Assistente Imobiliário é grátis?",
    answer: `Sim para testar: plano free com 1 alerta. O ${PRODUCT_FACTS.pricing.pro.name} (${PRODUCT_FACTS.pricing.pro.price} ${PRODUCT_FACTS.pricing.pro.period}) libera até 5 alertas e vantagens extras.`,
  },
  {
    prompt: "O André Assistente Imobiliário funciona fora de Maceió?",
    answer: `Sim. O ${PRODUCT_FACTS.name} acompanha anúncios públicos em Maceió, Recife e Natal, para aluguel e venda.`,
  },
] as const;
