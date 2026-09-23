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

function medianPhrase(value: number | null | undefined, label: string): string {
  if (value == null) return `${label}: sem mediana na amostra atual`;
  return `${label}: ${formatBRL(value)}`;
}

export function hubMetadata(): LocationMetadataCopy {
  return {
    title: `Imóveis no OLX por cidade e bairro | ${SITE_NAME}`,
    description:
      "Preços pedidos no OLX em Maceió, Recife e Natal: medianas por bairro com dados reais do mercado. Configure alertas no Telegram.",
    keywords: [
      "imóveis OLX",
      "apartamento Maceió",
      "apartamento Recife",
      "preço imóvel bairro",
    ],
    headline: "Imóveis por cidade",
    intro:
      "Páginas com estatísticas do OLX (mediana e amostra) por bairro. Use os números para calibrar sua busca e monte um alerta no Telegram.",
    alertSection:
      "No bot, escolha aluguel ou venda, bairros e faixa de preço — por exemplo, apartamento em Ponta Verde até R$ 400 mil na venda.",
    faq: [
      {
        question: "De onde vêm os preços?",
        answer:
          "São medianas do preço pedido em anúncios ativos do OLX, agregados pelo Imóvel Radar. Não listamos anúncios individuais nestas páginas.",
      },
      {
        question: "Como recebo imóveis novos?",
        answer:
          "Abra o bot no Telegram, crie um alerta com bairro e preço e receba matches quando surgir anúncio compatível.",
      },
    ],
  };
}

export function cityMetadata(city: CityPageData): LocationMetadataCopy {
  const vendaMedian = city.kinds.venda.median_price;
  const aluguelMedian = city.kinds.aluguel.median_price;
  const nbhdCount = city.neighbourhoods.length;

  return {
    title: `Imóveis em ${city.municipality}: preços OLX por bairro | ${SITE_NAME}`,
    description: `Mediana de venda ${formatBRL(vendaMedian)} e aluguel ${formatBRL(aluguelMedian)} em ${city.municipality}. ${nbhdCount} bairros com amostra confiável no OLX. Alertas no Telegram.`,
    keywords: [
      `imóvel ${city.municipality}`,
      `apartamento ${city.municipality}`,
      `OLX ${city.municipality}`,
      `preço imóvel ${city.municipality}`,
    ],
    headline: `Imóveis em ${city.municipality}`,
    intro: `Mercado OLX em ${city.municipality}: ${medianPhrase(vendaMedian, "mediana de venda na cidade")}; ${medianPhrase(aluguelMedian, "mediana de aluguel")}. Abaixo, bairros com amostra suficiente para comparação.`,
    alertSection: `No Telegram, selecione ${city.municipality}, o tipo (aluguel ou venda), bairros e teto de preço — por exemplo venda até o P75 do bairro que você quer.`,
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
  const vendaMedian = venda?.median_price ?? null;
  const vendaP75 = nbhd.venda.cityP75;
  const aluguelMedian = aluguel?.median_price ?? null;

  const descriptionParts = [
    `Preços no OLX em ${nbhd.name}, ${nbhd.municipality}.`,
    vendaMedian != null ? `Venda: mediana ${formatBRL(vendaMedian)}` : null,
    aluguelMedian != null ? `Aluguel: mediana ${formatBRL(aluguelMedian)}` : null,
    "Alertas por bairro no Telegram.",
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
    alertSection: buildAlertSection(nbhd, vendaMedian, vendaP75),
    faq: buildNeighbourhoodFaq(nbhd),
  };
}

function buildNeighbourhoodIntro(nbhd: NeighbourhoodPageData): string {
  const parts: string[] = [];
  const v = nbhd.venda.stat;
  const a = nbhd.aluguel.stat;

  if (v?.ranked && v.median_price != null) {
    const city = nbhd.venda.cityMedian;
    const vsCity =
      city != null && city > 0
        ? v.median_price > city
          ? "acima da mediana da cidade"
          : v.median_price < city
            ? "abaixo da mediana da cidade"
            : "na mediana da cidade"
        : "";
    parts.push(
      `Venda: mediana ${formatBRL(v.median_price)} (${v.sample} anúncios na amostra${vsCity ? `, ${vsCity}` : ""}).`
    );
  }

  if (a?.ranked && a.median_price != null) {
    parts.push(
      `Aluguel: mediana ${formatBRL(a.median_price)} (${a.sample} anúncios na amostra).`
    );
  }

  if (parts.length === 0) {
    return `Estatísticas do OLX para ${nbhd.name} em ${nbhd.municipality}.`;
  }

  return parts.join(" ");
}

function buildAlertSection(
  nbhd: NeighbourhoodPageData,
  vendaMedian: number | null,
  cityP75: number | null
): string {
  const examples: string[] = [];
  if (vendaMedian != null) {
    const cap = Math.round(vendaMedian * 1.15 / 1000) * 1000;
    examples.push(`venda em ${nbhd.name} até cerca de ${formatBRL(cap)}`);
  } else if (cityP75 != null) {
    examples.push(`venda em ${nbhd.name} até ${formatBRL(cityP75)} (referência P75 da cidade)`);
  }
  examples.push(`aluguel em ${nbhd.name} com teto no seu orçamento`);

  return `No bot do Telegram, escolha ${nbhd.municipality}, marque ${nbhd.name} e defina ${examples.join(" ou ")}. Você recebe aviso quando surgir anúncio compatível — sem precisar vasculhar o OLX todo dia.`;
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
        "Sim. No wizard do bot você escolhe categorias (apartamento, casa, etc.) além de bairro e preço.",
    },
  ];
}

export function dataFreshnessLabel(collectedAt: string): string {
  return `Dados do OLX coletados em ${formatCollectedAt(collectedAt)}.`;
}
