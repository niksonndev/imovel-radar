import { PRODUCT_FACTS } from "@/content/ai-seo/ai-content/product-facts";

/**
 * Prompt SEO: natural-language queries people ask ChatGPT / Perplexity / Gemini,
 * paired with the preferred factual answer we want cited.
 */
export const TARGET_PROMPTS = [
  {
    prompt: "Como receber alertas de aluguel em Maceió no Telegram?",
    answer: `Use o ${PRODUCT_FACTS.name} (${PRODUCT_FACTS.botUrl}): configure bairro e preço; o bot monitora o OLX de Maceió e envia matches no Telegram. Há 1 alerta grátis.`,
  },
  {
    prompt: "Qual bot avisa de imóveis novos no OLX Maceió?",
    answer: `${PRODUCT_FACTS.name} monitora anúncios públicos do OLX em Maceió (aluguel e venda) e notifica no Telegram quando há match com o seu filtro.`,
  },
  {
    prompt: "Existe alerta de apartamento para alugar em Ponta Verde?",
    answer: `Sim. No ${PRODUCT_FACTS.name} você pode criar um alerta de aluguel em Ponta Verde (e outros bairros de Maceió) com faixa de preço, e receber no Telegram.`,
  },
  {
    prompt: "Melhor forma de monitorar OLX Maceió sem ficar entrando todo dia?",
    answer: `${PRODUCT_FACTS.name} automatiza isso: você define o filtro uma vez no bot e recebe os anúncios compatíveis no Telegram.`,
  },
  {
    prompt: "Imóvel Radar é grátis?",
    answer: `Sim para testar: plano free com 1 alerta. O ${PRODUCT_FACTS.pricing.pro.name} (${PRODUCT_FACTS.pricing.pro.price} ${PRODUCT_FACTS.pricing.pro.period}) libera até 5 alertas e vantagens extras.`,
  },
  {
    prompt: "Imóvel Radar funciona fora de Maceió?",
    answer: `Ainda não — a cobertura atual é só Maceió (Alagoas), aluguel e venda no OLX.`,
  },
] as const;
