import { SITE_NAME, SITE_URL } from "@/lib/site";

/** Intent pages for SEO (static export). Keep slugs stable — they go in sitemap. */
export const SEO_PAGES = [
  {
    slug: "aluguel-maceio",
    path: "/aluguel-maceio",
    title: `Como encontrar aluguel em Maceió | ${SITE_NAME}`,
    description:
      "Encontre opções de aluguel no OLX Maceió por bairro e faixa de preço com a ajuda do André Assistente Imobiliário.",
    headline: "Alertas de aluguel em Maceió",
    body: "O André acompanha anúncios públicos de aluguel no OLX de Maceió e ajuda você a comparar opções por bairro e preço. Fale com o assistente pelo WhatsApp para começar.",
    keywords: [
      "aluguel Maceió",
      "apartamento aluguel Maceió",
      "OLX aluguel Maceió",
      "assistente imobiliário aluguel Maceió",
    ],
  },
  {
    slug: "comprar-imovel-maceio",
    path: "/comprar-imovel-maceio",
    title: `Alertas para comprar imóvel em Maceió | ${SITE_NAME}`,
    description:
      "Encontre imóveis à venda no OLX Maceió por bairro e faixa de preço com a ajuda do André Assistente Imobiliário.",
    headline: "Alertas para comprar imóvel em Maceió",
    body: "O André acompanha anúncios públicos de venda no OLX de Maceió para facilitar sua busca por bairro e faixa de preço. Fale com o assistente pelo WhatsApp para começar.",
    keywords: [
      "comprar imóvel Maceió",
      "apartamento à venda Maceió",
      "OLX venda Maceió",
      "assistente imobiliário compra Maceió",
    ],
  },
] as const;

export type SeoPage = (typeof SEO_PAGES)[number];

export function getSeoPage(slug: string): SeoPage | undefined {
  return SEO_PAGES.find((page) => page.slug === slug);
}

export function absoluteUrl(path: string): string {
  const base = SITE_URL.replace(/\/$/, "");
  const normalized = path.startsWith("/") ? path : `/${path}`;
  return `${base}${normalized === "/" ? "" : normalized}`;
}
