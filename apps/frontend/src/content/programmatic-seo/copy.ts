import type { CityPageData, NeighbourhoodPageData } from "@/content/programmatic-seo/catalog";
import { formatBRL, formatCollectedAt } from "@/lib/market-stats";
import { SITE_NAME } from "@/lib/site";

export type LocationMetadataCopy = {
  title: string;
  description: string;
  keywords: string[];
  headline: string;
  intro: string;
  alertSection: string;
  faq: { question: string; answer: string }[];
};

function meanPhrase(value: number | null | undefined, label: string): string {
  if (value == null) return `${label}: sem média na amostra atual`;
  return `${label}: ${formatBRL(value)}`;
}

export function hubMetadata(): LocationMetadataCopy {
  return {
    title: `Imóveis no OLX por cidade e bairro | ${SITE_NAME}`,
    description:
      "Preços pedidos no OLX em Maceió, Recife e Natal: médias por bairro com dados reais do mercado. Fale com André pelo WhatsApp para acompanhar opções.",
    keywords: [
      "imóveis OLX",
      "apartamento Maceió",
      "apartamento Recife",
      "preço imóvel bairro",
    ],
    headline: "Imóveis por cidade",
    intro:
      "Páginas com estatísticas do OLX (média e amostra) por bairro. Use os números para calibrar sua busca por imóvel.",
    alertSection:
      "O André ajuda a encontrar opções de aluguel ou venda por bairro e faixa de preço. Converse com o assistente pelo WhatsApp.",
    faq: [
      {
        question: "De onde vêm os preços?",
        answer:
          "São médias do preço pedido em anúncios ativos do OLX, agregados pelo André Assistente Imobiliário. Não listamos anúncios individuais nestas páginas.",
      },
      {
        question: "Como recebo imóveis novos?",
        answer:
          "Converse com André pelo WhatsApp para acompanhar opções compatíveis com sua busca.",
      },
    ],
  };
}

export function cityMetadata(city: CityPageData): LocationMetadataCopy {
  const vendaMean = city.kinds.venda.mean_price;
  const aluguelMean = city.kinds.aluguel.mean_price;
  const nbhdCount = city.neighbourhoods.length;

  return {
    title: `Imóveis em ${city.municipality}: preços OLX por bairro | ${SITE_NAME}`,
    description: `Média de venda ${formatBRL(vendaMean)} e aluguel ${formatBRL(aluguelMean)} em ${city.municipality}. ${nbhdCount} bairros com amostra confiável no OLX.`,
    keywords: [
      `imóvel ${city.municipality}`,
      `apartamento ${city.municipality}`,
      `OLX ${city.municipality}`,
      `preço imóvel ${city.municipality}`,
    ],
    headline: `Imóveis em ${city.municipality}`,
    intro: `Mercado OLX em ${city.municipality}: ${meanPhrase(vendaMean, "média de venda na cidade")}; ${meanPhrase(aluguelMean, "média de aluguel")}. Abaixo, bairros com amostra suficiente para comparação.`,
    alertSection: `Compare os preços de aluguel e venda em ${city.municipality} e converse com André pelo WhatsApp para acompanhar opções compatíveis.`,
    faq: [
      {
        question: `Quantos bairros aparecem em ${city.municipality}?`,
        answer: `Listamos ${nbhdCount} bairros com pelo menos a amostra mínima usada no painel de mercado (anúncios ativos com preço válido).`,
      },
      {
        question: "Os valores são negociados?",
        answer:
          "Não. Mostramos o preço pedido nos anúncios; a negociação é entre você e o anunciante.",
      },
    ],
  };
}

export function neighbourhoodMetadata(nbhd: NeighbourhoodPageData): LocationMetadataCopy {
  const venda = nbhd.venda.stat;
  const aluguel = nbhd.aluguel.stat;
  const vendaMean = venda?.mean_price ?? null;
  const vendaP75 = nbhd.venda.cityP75;
  const aluguelMean = aluguel?.mean_price ?? null;

  const descriptionParts = [
    `Preços no OLX em ${nbhd.name}, ${nbhd.municipality}.`,
    vendaMean != null ? `Venda: média ${formatBRL(vendaMean)}` : null,
    aluguelMean != null ? `Aluguel: média ${formatBRL(aluguelMean)}` : null,
    "Compare anúncios por bairro com a ajuda do André Assistente Imobiliário.",
  ].filter(Boolean);

  return {
    title: `Imóveis em ${nbhd.name}, ${nbhd.municipality} | ${SITE_NAME}`,
    description: descriptionParts.join(" "),
    keywords: [
      `apartamento ${nbhd.name}`,
      `imóvel ${nbhd.name} ${nbhd.municipality}`,
      `OLX ${nbhd.name}`,
      `preço ${nbhd.name}`,
    ],
    headline: `${nbhd.name}, ${nbhd.municipality}`,
    intro: buildNeighbourhoodIntro(nbhd),
    alertSection: buildAlertSection(nbhd, vendaMean, vendaP75),
    faq: buildNeighbourhoodFaq(nbhd),
  };
}

function buildNeighbourhoodIntro(nbhd: NeighbourhoodPageData): string {
  const parts: string[] = [];
  const v = nbhd.venda.stat;
  const a = nbhd.aluguel.stat;

  if (v?.ranked && v.mean_price != null) {
    const city = nbhd.venda.cityMedian;
    const vsCity =
      city != null && city > 0
        ? v.mean_price > city
          ? "acima da média da cidade"
          : v.mean_price < city
            ? "abaixo da média da cidade"
            : "na média da cidade"
        : "";
    parts.push(
      `Venda: média ${formatBRL(v.mean_price)} (${v.sample} anúncios na amostra${vsCity ? `, ${vsCity}` : ""}).`
    );
  }

  if (a?.ranked && a.mean_price != null) {
    parts.push(
      `Aluguel: média ${formatBRL(a.mean_price)} (${a.sample} anúncios na amostra).`
    );
  }

  if (parts.length === 0) {
    return `Estatísticas do OLX para ${nbhd.name} em ${nbhd.municipality}.`;
  }

  return parts.join(" ");
}

function buildAlertSection(
  nbhd: NeighbourhoodPageData,
  vendaMean: number | null,
  cityP75: number | null
): string {
  const examples: string[] = [];
  if (vendaMean != null) {
    const cap = Math.round(vendaMean * 1.15 / 1000) * 1000;
    examples.push(`venda em ${nbhd.name} até cerca de ${formatBRL(cap)}`);
  } else if (cityP75 != null) {
    examples.push(`venda em ${nbhd.name} até ${formatBRL(cityP75)} (referência P75 da cidade)`);
  }
  examples.push(`aluguel em ${nbhd.name} com teto no seu orçamento`);

  return `Ao buscar imóvel em ${nbhd.name}, ${nbhd.municipality}, compare ${examples.join(" ou ")}. Converse com André pelo WhatsApp para acompanhar opções compatíveis sem precisar vasculhar o OLX todo dia.`;
}

function buildNeighbourhoodFaq(
  nbhd: NeighbourhoodPageData
): { question: string; answer: string }[] {
  const collected = formatCollectedAt(nbhd.collectedAt);
  return [
    {
      question: `Quando estes dados de ${nbhd.name} foram atualizados?`,
      answer: `Coleta do snapshot de mercado em ${collected}. O painel completo está em Mercado no site.`,
    },
    {
      question: `Posso filtrar só apartamento em ${nbhd.name}?`,
      answer:
        "Sim. Você pode incluir categorias (apartamento, casa, etc.) além de bairro e preço na sua busca.",
    },
  ];
}

export function dataFreshnessLabel(collectedAt: string): string {
  return `Dados do OLX coletados em ${formatCollectedAt(collectedAt)}.`;
}
