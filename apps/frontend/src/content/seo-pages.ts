import { SITE_NAME, SITE_URL } from "@/lib/site";

/** Intent pages for SEO (static export). Keep slugs stable — they go in sitemap. */
export const SEO_PAGES = [
  {
    slug: "aluguel-maceio",
    path: "/aluguel-maceio",
    title: `Alertas de aluguel em Maceió no Telegram | ${SITE_NAME}`,
    description:
      "Receba no Telegram anúncios novos de aluguel no OLX Maceió. Filtre por bairro e preço — comece grátis, Radar Pro via Pix.",
    headline: "Alertas de aluguel em Maceió",
    body: "Monitore o OLX de Maceió e receba no Telegram quando aparecer um aluguel que bata com o seu filtro de bairro e preço. Plano free com 1 alerta; Radar Pro via Pix para quem precisa de mais.",
    keywords: [
      "aluguel Maceió",
      "apartamento aluguel Maceió",
      "OLX aluguel Maceió",
      "alerta aluguel Telegram",
    ],
  },
  {
    slug: "comprar-imovel-maceio",
    path: "/comprar-imovel-maceio",
    title: `Alertas para comprar imóvel em Maceió | ${SITE_NAME}`,
    description:
      "Monitore vendas no OLX Maceió e receba alertas no Telegram. Comece grátis; upgrade Radar Pro pago via Pix.",
    headline: "Alertas para comprar imóvel em Maceió",
    body: "Acompanhe anúncios de venda no OLX Maceió sem checar o site todo dia. Defina bairros e faixa de preço no bot; no free você tem 1 alerta, no Pro (Pix) até 5 e queda de preço.",
    keywords: [
      "comprar imóvel Maceió",
      "apartamento à venda Maceió",
      "OLX venda Maceió",
      "alerta imóvel Telegram",
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
