// ------------------------------------------------------------------
// Content for André Assistente Imobiliário landing page.
// Edit this file to update ALL copy — no component changes needed.
// ------------------------------------------------------------------

export const WHATSAPP_ASSISTANT_URL = 'https://wa.me/5582993345293';
export const ASSISTANT_UPDATES_URL = '/novidades';
export const SUPPORT_URL = process.env.NEXT_PUBLIC_SUPPORT_URL?.trim() ?? '';

// Hero (outcome-first)
export const HERO_HEADLINE = 'Encontre seu próximo imóvel.';
export const HERO_HEADLINE_LINE2 = 'Conte com o André.';
export const HERO_SUBHEADLINE =
  'O André acompanha anúncios públicos e ajuda você a encontrar imóveis que combinam com o que procura.';
export const HERO_CTA_LABEL = 'Conversar com André no WhatsApp';
export const HERO_CTA_HINT =
  'Tire dúvidas e conte o que procura.';

// Assistant conversation preview (hero product visual)
export const MOCK_ALERT = {
  appName: 'André',
  time: '10:12',
  title: '🔥 Novo imóvel com 97% de match',
  property: 'Apartamento em Ponta Verde',
  price: 'R$ 1.800/mês',
  details: '2 quartos · 65m²',
  alertLabel: 'Seu alerta',
  alertFilter: 'Ponta Verde · até R$2.000',
  cta: 'Ver no OLX →',
} as const;

// How it works (headline → solution → outcome steps)
export const HOW_IT_WORKS_SOLUTION =
  'Deixe o André encontrar os anúncios por você.';
export const HOW_IT_WORKS_HEADLINE =
  'Você explica o que procura. O André acompanha.';
export const STEP_1_TITLE = 'Diga o que procura';
export const STEP_1_DESC = 'Aluguel · Ponta Verde · até R$2.000';
export const STEP_2_TITLE = 'O André monitora';
export const STEP_2_DESC = '17 anúncios novos encontrados';
export const STEP_3_TITLE = 'Você recebe o match';
export const STEP_3_DESC = 'WhatsApp · “Novo imóvel com 97% de match”';

// Example searches (“Does it work in my case?”)
export const EXAMPLE_SEARCHES_HEADLINE = 'Funciona no seu caso';
export const EXAMPLE_SEARCHES_SUBHEADLINE =
  'Exemplos de alertas que você pode montar em poucos toques.';
export const EXAMPLE_SEARCHES = [
  'Aluguel · Ponta Verde · até R$2.000',
  'Aluguel · Jatiúca · até R$2.500',
  'Compra · Farol · até R$350.000',
  'Compra · Pajuçara · até R$450.000',
] as const;
export const EXAMPLE_SEARCHES_CTA = 'Conversar com André';

// Pricing / freemium
export const PRICING_HEADLINE = 'Pode testar grátis. Evolua quando precisar.';
export const PRICING_SUBHEADLINE =
  'Comece com 1 alerta. Se precisar de mais, cadastre seu e-mail com o André e ganhe 1 mês do plano Pro.';
export const PRICING_FREE = {
  name: 'Free',
  price: 'R$ 0',
  period: 'para sempre no plano básico',
  cta: 'Conversar com André',
  features: [
    '1 alerta ativo',
    'Até 2 anúncios acompanhados',
    'Resumo diário pelo WhatsApp',
    'Aluguel e venda em Maceió e Recife',
    'Link direto pro anúncio no OLX',
  ],
} as const;
export const PRICING_PRO = {
  name: 'André Pro',
  price: '1 mês grátis',
  period: 'com e-mail para o André',
  badge: 'Recomendado',
  cta: 'Falar com André no WhatsApp',
  features: [
    'Até 5 alertas ativos',
    'Até 10 anúncios acompanhados',
    'Prioridade nos matches',
    'Alertas de queda de preço',
    'Atualizações mais frequentes (quando disponíveis)',
  ],
} as const;
export const PRICING_FOOTNOTE =
  'O plano Pro libera 1 mês grátis após o cadastro do e-mail. Informações sobre a disponibilidade serão publicadas em Novidades.';

// FAQ
export const FAQ_HEADLINE = 'Perguntas frequentes';
export const FAQ_ITEMS = [
  {
    question: 'Preciso criar conta ou pagar pra testar?',
    answer:
      'Não. O André oferece um alerta grátis; as novidades sobre como começar serão publicadas neste site.',
  },
  {
    question: 'Funciona pra aluguel e venda?',
    answer:
      'Sim. Você escolhe se quer alugar ou comprar e monta o alerta com bairro e faixa de preço.',
  },
  {
    question: 'Só funciona em Maceió?',
    answer: 'Hoje o Radar monitora anúncios do OLX em Maceió e em Recife.',
  },
  {
    question: 'De onde vêm os anúncios?',
    answer:
      'Dos anúncios públicos do OLX em Maceió e Recife. Somos um produto independente e não somos afiliados à OLX.',
  },
  {
    question: 'O que muda no André Pro?',
    answer:
      'No Pro você pode ter até 5 alertas e até 10 anúncios acompanhados, além de outras vantagens. O plano oferece 1 mês grátis com cadastro de e-mail.',
  },
  {
    question: 'Como ganho 1 mês do André Pro?',
    answer:
      'Quando o cadastro estiver disponível, informe seu e-mail ao André. O benefício é liberado uma vez por conta.',
  },
  {
    question: 'Com que frequência chegam os alertas?',
    answer:
      'O André envia um resumo dos imóveis que combinam com seu filtro. A frequência varia conforme a coleta de anúncios.',
  },
] as const;

// CTA section
export const CTA_HEADLINE = 'Deixe o André procurar por você';
export const CTA_SUBHEADLINE =
  'Conte ao André o que você procura e receba ajuda pelo WhatsApp.';
export const CTA_BUTTON_LABEL = 'Falar com André no WhatsApp';

// Shared section CTA (intent pages + how-it-works)
export const SECTION_CTA_LABEL = 'Começar grátis';

// Open Graph / SEO taglines
export const OG_IMAGE_TAGLINE =
  'André Assistente Imobiliário — encontre imóveis que combinam com você';

// Marquee
export const MARQUEE_LABEL = 'Bairros em Maceió · aluguel e venda';
export const MONITORED_NEIGHBORHOODS = [
  'Ponta Verde',
  'Jatiúca',
  'Pajuçara',
  'Mangabeiras',
  'Cruz das Almas',
  'Benedito Bentes',
  'Tabuleiro do Martins',
  'Farol',
  'Jacarecica',
  'Antares',
  'Serraria',
  'Riacho Doce',
];

// Footer / trust
export const FOOTER_ASSISTANT_LABEL = 'Falar com André no WhatsApp';
export const FOOTER_LEGAL = '© André Assistente Imobiliário';
export const FOOTER_DISCLAIMER =
  'Produto independente. Não somos afiliados à OLX. Monitoramos anúncios públicos de Maceió, Recife e Natal; preços e disponibilidade podem mudar.';
export const FOOTER_PRIVACY =
  'O André usa os dados necessários para encontrar imóveis compatíveis e atender você pelo WhatsApp. Consulte a Política de Privacidade.';
export const FOOTER_CONTACT_LABEL = SUPPORT_URL
  ? 'Contato e suporte'
  : 'Novidades do André';
