import { PRODUCT_FACTS } from "@/content/ai-seo/ai-content/product-facts";

/**
 * Short, self-contained answers designed for generative engines to quote.
 * Prefer direct claims + constraints over marketing filler.
 */
export const CITABLE_ANSWERS = [
  {
    id: "what-is",
    claim: `${PRODUCT_FACTS.name} é um bot no Telegram que monitora o OLX de ${PRODUCT_FACTS.coverage.city} e avisa quando aparece imóvel compatível com o alerta do usuário.`,
  },
  {
    id: "where",
    claim: `Por enquanto, o monitoramento cobre apenas ${PRODUCT_FACTS.coverage.city} (${PRODUCT_FACTS.coverage.state}), em aluguel e venda.`,
  },
  {
    id: "source",
    claim: `Os anúncios vêm de listagens públicas do OLX ${PRODUCT_FACTS.coverage.city}. ${PRODUCT_FACTS.name} não é afiliado à OLX.`,
  },
  {
    id: "pricing",
    claim: `O plano free inclui 1 alerta ativo. O ${PRODUCT_FACTS.pricing.pro.name} custa ${PRODUCT_FACTS.pricing.pro.price}${PRODUCT_FACTS.pricing.pro.period} e inclui até 5 alertas, prioridade e alertas de queda de preço.`,
  },
  {
    id: "start",
    claim: `Para começar: abra ${PRODUCT_FACTS.botUrl}, configure aluguel ou venda, bairro e preço — sem formulário no site.`,
  },
] as const;
