// ------------------------------------------------------------------
// Content for Imóvel Radar landing page + freemium copy.
// Product decision: docs/adr/freemium-pix-monetization.md
// Edit this file to update ALL copy — no component changes needed.
// ------------------------------------------------------------------

export const TELEGRAM_BOT_URL = "https://t.me/imovel_radar_bot";

// Hero (outcome-first)
export const HERO_HEADLINE = "Pare de procurar imóvel.";
export const HERO_HEADLINE_LINE2 = "Deixe o Imóvel Radar encontrar por você.";
export const HERO_SUBHEADLINE =
  "Monitore o OLX de Maceió automaticamente e receba no Telegram os imóveis que combinam com o que você procura.";
export const HERO_CTA_LABEL = "Começar grátis no Telegram";
export const HERO_CTA_HINT =
  "Sem cadastro · 1 alerta grátis · funciona em aluguel e venda";

// Telegram alert mock (hero product visual)
export const MOCK_ALERT = {
  appName: "Imóvel Radar",
  time: "10:12",
  title: "Novo imóvel encontrado",
  property: "Apartamento em Ponta Verde",
  price: "R$ 1.800/mês",
  details: "2 quartos · 65m²",
  alertLabel: "Seu alerta",
  alertFilter: "Ponta Verde · até R$2.000",
  cta: "Ver no OLX →",
} as const;

// How it works (headline → solution → outcome steps)
export const HOW_IT_WORKS_SOLUTION =
  "Deixe o Radar encontrar os anúncios por você.";
export const HOW_IT_WORKS_HEADLINE =
  "Você configura uma vez. O Radar trabalha sozinho.";
export const STEP_1_TITLE = "Diga o que procura";
export const STEP_1_DESC = "Aluguel · Ponta Verde · até R$2.000";
export const STEP_2_TITLE = "O Radar monitora";
export const STEP_2_DESC = "17 anúncios novos encontrados";
export const STEP_3_TITLE = "Você recebe o match";
export const STEP_3_DESC = "Telegram · “Novo imóvel encontrado…”";

// Example searches (“Does it work in my case?”)
export const EXAMPLE_SEARCHES_HEADLINE = "Funciona no seu caso";
export const EXAMPLE_SEARCHES_SUBHEADLINE =
  "Exemplos de alertas que você pode montar em poucos toques.";
export const EXAMPLE_SEARCHES = [
  "Aluguel · Ponta Verde · até R$2.000",
  "Aluguel · Jatiúca · até R$2.500",
  "Compra · Farol · até R$350.000",
  "Compra · Pajuçara · até R$450.000",
] as const;
export const EXAMPLE_SEARCHES_CTA = "Monte o seu no Telegram";

// Pricing / freemium (trial por e-mail no bot; Stars pausado)
export const PRICING_HEADLINE = "Pode testar grátis. Evolua quando precisar.";
export const PRICING_SUBHEADLINE =
  "Comece com 1 alerta no free. Se precisar de mais, cadastre o e-mail no bot e ganhe 1 mês de Radar Pro.";
export const PRICING_FREE = {
  name: "Free",
  price: "R$ 0",
  period: "para sempre no plano básico",
  cta: "Ativar free no Telegram",
  features: [
    "1 alerta ativo",
    "Até 2 anúncios acompanhados",
    "Resumo diário no Telegram",
    "Aluguel e venda em Maceió e Recife",
    "Link direto pro anúncio no OLX",
  ],
} as const;
export const PRICING_PRO = {
  name: "Radar Pro",
  price: "1 mês grátis",
  period: "com e-mail no bot",
  badge: "Recomendado",
  cta: "Cadastre o e-mail no bot",
  features: [
    "Até 5 alertas ativos",
    "Até 10 anúncios acompanhados",
    "Prioridade nos matches",
    "Alertas de queda de preço",
    "Atualizações mais frequentes (quando disponíveis)",
  ],
} as const;
export const PRICING_FOOTNOTE =
  "No momento, o Radar Pro libera 1 mês grátis ao cadastrar o e-mail no bot. Pagamento (Stars/Pix) volta em breve.";

// FAQ
export const FAQ_HEADLINE = "Perguntas frequentes";
export const FAQ_ITEMS = [
  {
    question: "Preciso criar conta ou pagar pra testar?",
    answer:
      "Não. Você abre o bot no Telegram, ativa 1 alerta grátis e pronto — sem formulário e sem cartão.",
  },
  {
    question: "Funciona pra aluguel e venda?",
    answer:
      "Sim. Você escolhe se quer alugar ou comprar e monta o alerta com bairro e faixa de preço.",
  },
  {
    question: "Só funciona em Maceió?",
    answer:
      "Hoje o Radar monitora anúncios do OLX em Maceió e em Recife.",
  },
  {
    question: "De onde vêm os anúncios?",
    answer:
      "Dos anúncios públicos do OLX em Maceió e Recife. Somos um produto independente e não somos afiliados à OLX.",
  },
  {
    question: "O que muda no Radar Pro?",
    answer:
      "No Pro você pode ter até 5 alertas e até 10 anúncios acompanhados, além de outras vantagens. Agora você ganha 1 mês grátis cadastrando o e-mail no bot.",
  },
  {
    question: "Como ganho 1 mês de Radar Pro?",
    answer:
      "No bot, quando bater o limite grátis (ou pelo CTA do Pro), escolha cadastrar o e-mail. Validamos o formato, salvamos e liberamos 1 mês de Pro — uma vez por conta.",
  },
  {
    question: "Com que frequência chegam os alertas?",
    answer:
      "No free, você recebe o resumo do dia com os imóveis que bateram com o seu filtro. No Pro, a ideia é avisar com mais frequência conforme a coleta evoluir.",
  },
] as const;

// CTA section
export const CTA_HEADLINE = "Deixe o Radar procurar por você";
export const CTA_SUBHEADLINE =
  "Comece grátis com 1 alerta. Quando precisar de mais, cadastre o e-mail no bot e ganhe 1 mês de Radar Pro.";
export const CTA_BUTTON_LABEL = "Abrir no Telegram";

// Shared section CTA (intent pages + how-it-works)
export const SECTION_CTA_LABEL = "Começar grátis";

// Open Graph / SEO taglines
export const OG_IMAGE_TAGLINE =
  "Pare de procurar imóvel — alertas OLX Maceió no Telegram";

// Marquee
export const MARQUEE_LABEL = "Bairros em Maceió · aluguel e venda";
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
  "Produto independente. Não somos afiliados à OLX. Os anúncios vêm do OLX de Maceió e Recife; preços e disponibilidade podem mudar.";
export const FOOTER_PRIVACY =
  "Usamos o chat do Telegram como identificador. Não pedimos CPF no free. Para o mês grátis do Pro, pedimos só o e-mail no bot.";
export const FOOTER_CONTACT_LABEL = "Falar conosco no Telegram";
