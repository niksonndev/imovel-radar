// ------------------------------------------------------------------
// Content for Imóvel Radar landing page + freemium/Pix copy.
// Product decision: docs/adr/freemium-pix-monetization.md
// Edit this file to update ALL copy — no component changes needed.
// ------------------------------------------------------------------

export const TELEGRAM_BOT_URL = "https://t.me/imovel_radar_bot";

// Hero
export const HERO_HEADLINE = "Não perca mais nenhum anúncio bom no OLX";
export const HERO_SUBHEADLINE =
  "Monitore aluguel e venda em Maceió e receba no Telegram os anúncios novos que batem com o seu filtro — comece grátis, sem cadastro.";
export const HERO_BADGE_TEXT = "Coleta diária · aluguel e venda em Maceió";
export const HERO_CTA_LABEL = "Comece grátis no Telegram";
export const HERO_CTA_HINT = "1 alerta grátis · upgrade via Pix quando precisar";

// Social proof
export const SOCIAL_PROOF_HEADLINE = "Feito pra quem busca imóvel em Maceió";
export const SOCIAL_PROOF_STATS = [
  { value: "17k+", label: "anúncios indexados no OLX Maceió" },
  { value: "Diário", label: "varredura de aluguel e venda" },
  { value: "Pix", label: "assinatura Pro sem cartão internacional" },
] as const;
/** Cenários de uso (não são depoimentos de clientes). */
export const SOCIAL_PROOF_QUOTES = [
  {
    quote:
      "Aluguel na orla: um alerta de bairro + faixa de preço e o digest do dia chega no Telegram, sem F5 no OLX.",
    attribution: "Cenário · Aluguel em Ponta Verde / Jatiúca",
  },
  {
    quote:
      "Compra com orçamento apertado: no free você valida o fluxo; no Pro (Pix) acompanha vários bairros e quedas de preço.",
    attribution: "Cenário · Compra em Maceió",
  },
] as const;

// Features (no per-card CTA — one primary path on the page)
export const FEATURE_1_TITLE = "Monitore";
export const FEATURE_1_DESC =
  "Todo dia o radar varre o OLX de Maceió em busca de anúncios novos de aluguel e venda — sem você precisar abrir a aba de novo.";
export const FEATURE_2_TITLE = "Filtre";
export const FEATURE_2_DESC =
  "Escolha bairro, faixa de preço e se quer alugar ou comprar. Você só recebe o que bate com o alerta.";
export const FEATURE_3_TITLE = "Receba";
export const FEATURE_3_DESC =
  "Quando aparece match, o resumo chega no Telegram com link direto pro anúncio — antes de sumir no meio do feed.";

// How it works (order matches Telegram UX: open bot → filters → alerts)
export const HOW_IT_WORKS_HEADLINE = "Como funciona";
export const STEP_1_TITLE = "Abra o bot no Telegram";
export const STEP_1_DESC =
  "Sem formulário e sem cartão no free: toque em iniciar e pronto.";
export const STEP_2_TITLE = "Monte seu alerta";
export const STEP_2_DESC =
  "Defina aluguel ou compra, bairros e faixa de preço em poucos toques.";
export const STEP_3_TITLE = "Receba os matches";
export const STEP_3_DESC =
  "Todo anúncio novo que bater com o filtro chega no seu Telegram.";

// Pricing / freemium (Pix)
export const PRICING_HEADLINE = "Comece grátis. Evolua com Pix.";
export const PRICING_SUBHEADLINE =
  "O free prova o valor. O Radar Pro desbloqueia mais alertas e vantagens — pagamento via Pix, sem Telegram Stars.";
export const PRICING_FREE = {
  name: "Free",
  price: "R$ 0",
  period: "para sempre no plano básico",
  cta: "Ativar free no Telegram",
  features: [
    "1 alerta ativo",
    "Digest diário (coleta + notificação do dia)",
    "Aluguel e venda em Maceió",
    "Carrossel com link direto pro OLX",
  ],
} as const;
export const PRICING_PRO = {
  name: "Radar Pro",
  price: "R$ 19,90",
  period: "/ mês via Pix",
  badge: "Recomendado",
  cta: "Quero o Pro no bot",
  features: [
    "Até 5 alertas ativos",
    "Prioridade na fila de matches",
    "Alertas de queda de preço",
    "Atualizações mais frequentes (quando a coleta multi-dia estiver no ar)",
    "Filtros extras (ex.: com foto) conforme forem liberados",
  ],
} as const;
export const PRICING_FOOTNOTE =
  "Cobrança Pix em implementação. Enquanto isso, comece no free — o Pro será ativado no próprio bot.";

// CTA section
export const CTA_HEADLINE = "Comece a receber alertas agora";
export const CTA_SUBHEADLINE =
  "Comece grátis com 1 alerta. Quando precisar de mais, o Radar Pro entra via Pix.";
export const CTA_BUTTON_LABEL = "Abrir no Telegram";

// Sections
export const FEATURES_SECTION_HEADING = "O que o radar faz";
export const SECTION_CTA_LABEL = "Comece grátis";

// Open Graph / SEO taglines
export const OG_IMAGE_TAGLINE =
  "Alertas de imóveis OLX Maceió no Telegram — comece grátis";

// Telegram preview (mock de conversa — aluguel + venda)
export const TELEGRAM_PREVIEW_HEADLINE = "Veja como o alerta chega";
export const TELEGRAM_PREVIEW_SUBHEADLINE =
  "Resumo do anúncio e link direto no Telegram — aluguel ou venda, sem ficar F5 no OLX.";
export const MOCK_ALERTS = [
  {
    title: "Apartamento em Ponta Verde",
    detail: "R$ 1.800/mês · 2 quartos · 65m² · Aluguel",
    time: "10:12",
    kind: "aluguel" as const,
  },
  {
    title: "Apartamento em Jatiúca",
    detail: "R$ 320.000 · 3 quartos · 98m² · Venda",
    time: "10:14",
    kind: "venda" as const,
  },
];

// Marquee
export const MARQUEE_LABEL = "Bairros monitorados em Maceió · aluguel e venda";
export const MONITORED_NEIGHBORHOODS = [
  "Ponta Verde",
  "Jatiúca",
  "Pajuçara",
  "Mangabeiras",
  "Cruz das Almas",
  "Benedito Bentes",
  "Tabuleiro do Martins",
  "Farol",
  "Jacarecica",
  "Antares",
  "Serraria",
  "Riacho Doce",
];

// Footer / trust
export const FOOTER_TELEGRAM_LABEL = "Abrir bot no Telegram";
export const FOOTER_LEGAL = "© Imóvel Radar";
export const FOOTER_DISCLAIMER =
  "Produto independente. Não somos afiliados à OLX. Os anúncios vêm do OLX Maceió; preços e disponibilidade podem mudar.";
export const FOOTER_PRIVACY =
  "Usamos o chat do Telegram como identificador. Não pedimos CPF no free. Pagamentos Pro serão via Pix.";
export const FOOTER_CONTACT_LABEL = "Falar conosco no Telegram";
