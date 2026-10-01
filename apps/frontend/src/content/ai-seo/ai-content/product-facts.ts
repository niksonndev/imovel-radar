import {
  FAQ_ITEMS,
  MONITORED_NEIGHBORHOODS,
  PRICING_FREE,
  PRICING_PRO,
  WHATSAPP_ASSISTANT_URL,
} from "@/content/page-content";
import { SITE_DESCRIPTION, SITE_NAME, SITE_URL } from "@/lib/site";

/** Canonical product facts for AI citation and structured data. */
export const PRODUCT_FACTS = {
  name: SITE_NAME,
  tagline: "Assistente imobiliário para encontrar imóveis no OLX",
  description: SITE_DESCRIPTION,
  url: SITE_URL,
  whatsappUrl: WHATSAPP_ASSISTANT_URL,
  locale: "pt-BR",
  coverage: {
    city: "Maceió, Recife e Natal",
    state: "Alagoas, Pernambuco e Rio Grande do Norte",
    country: "Brasil",
    source: "OLX Maceió, Recife e Natal (anúncios públicos)",
    listingTypes: ["aluguel", "venda"] as const,
    neighborhoods: MONITORED_NEIGHBORHOODS,
  },
  pricing: {
    free: {
      name: PRICING_FREE.name,
      price: PRICING_FREE.price,
      features: [...PRICING_FREE.features],
    },
    pro: {
      name: PRICING_PRO.name,
      price: PRICING_PRO.price,
      period: PRICING_PRO.period,
      features: [...PRICING_PRO.features],
      payment: "1 mês grátis com cadastro de e-mail",
    },
  },
  independence:
    "Produto independente. Não afiliado à OLX. Anúncios vêm do OLX das cidades cobertas; preços e disponibilidade podem mudar.",
  howItWorks: [
    "A pessoa informa ao André se procura aluguel ou venda, bairros e faixa de preço.",
    "O André acompanha anúncios públicos do OLX em Maceió, Recife e Natal.",
    "Quando há match, André envia pelo WhatsApp o motivo (queda de preço, match alto, anúncio novo ou volta ao ar) e o link do anúncio.",
  ],
  faqs: FAQ_ITEMS.map((item) => ({
    question: item.question,
    answer: item.answer,
  })),
} as const;
