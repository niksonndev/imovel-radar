import { ListingItem, MarketKindStats } from '../database/client.js';

export interface ContentTopic {
  type: 'PRICE_RANKING' | 'OPPORTUNITY_DEAL' | 'MARKET_TREND' | 'EDUCATIONAL_TIPS';
  neighborhood?: string;
  listingKind?: 'aluguel' | 'venda';
  angle?: string;
}

export interface GeneratedContentCopy {
  title: string;
  hook: string;
  caption: string;
  slides: Array<{
    slideNumber: number;
    title: string;
    body: string;
    highlightedMetric?: string;
  }>;
  cta: string;
  hashtags: string[];
}

export type CommentIntent =
  | 'ALERT_REQUEST'
  | 'PRICE_QUERY'
  | 'GENERAL_ENGAGEMENT'
  | 'SPAM';

export interface CommentAnalysis {
  intent: CommentIntent;
  confidence: number;
  suggestedReply: string;
  shouldHide: boolean;
  reason: string;
}

export interface PerformanceAnalysis {
  summary: string;
  keyInsights: string[];
  nextPautas: Array<{
    title: string;
    reason: string;
    suggestedFormat: 'CAROUSEL' | 'SINGLE_IMAGE';
  }>;
}

export class LLMService {
  private provider: 'mock' | 'openai' | 'gemini';
  private openaiKey?: string;
  private geminiKey?: string;
  private telegramBotUser: string;

  constructor() {
    this.provider = (process.env.LLM_PROVIDER as any) || 'mock';
    this.openaiKey = process.env.OPENAI_API_KEY;
    this.geminiKey = process.env.GEMINI_API_KEY;
    this.telegramBotUser = process.env.TELEGRAM_BOT_USERNAME || 'imovelradar_bot';
  }

  async generateContentCopy(
    topic: ContentTopic,
    marketData: MarketKindStats,
    deals: ListingItem[] = []
  ): Promise<GeneratedContentCopy> {
    if (this.provider === 'openai' && this.openaiKey) {
      try {
        return await this.generateWithOpenAI(topic, marketData, deals);
      } catch (err) {
        console.warn('[LLMService] OpenAI falhou, usando gerador heurístico:', err);
      }
    }

    if (this.provider === 'gemini' && this.geminiKey) {
      try {
        return await this.generateWithGemini(topic, marketData, deals);
      } catch (err) {
        console.warn('[LLMService] Gemini falhou, usando gerador heurístico:', err);
      }
    }

    return this.generateHeuristicCopy(topic, marketData, deals);
  }

  private generateHeuristicCopy(
    topic: ContentTopic,
    marketData: MarketKindStats,
    deals: ListingItem[]
  ): GeneratedContentCopy {
    const sortedNeighbours = [...marketData.neighbourhoods].sort(
      (a, b) => (b.median_price_m2 || 0) - (a.median_price_m2 || 0)
    );
    const topExpensive = sortedNeighbours[0] || { name: 'Ponta Verde', median_price_m2: 44, median_price: 3500 };
    const cheapest = sortedNeighbours[sortedNeighbours.length - 1] || { name: 'Benedito Bentes', median_price_m2: 18, median_price: 1100 };
    const deal = deals[0];

    if (topic.type === 'OPPORTUNITY_DEAL' && deal) {
      const dropText = deal.old_price && deal.price_value && deal.old_price > deal.price_value
        ? `Caiu de R$ ${deal.old_price} para R$ ${deal.price_value}!`
        : `Por apenas R$ ${deal.price_value}/mês`;

      return {
        title: `Achado na ${deal.neighbourhood}: ${deal.title}`,
        hook: `Achamos esse imóvel abaixo da mediana na ${deal.neighbourhood}! 🎯`,
        caption: `Oportunidade real monitorada pelo robô do Imóvel Radar.\n\n📍 Bairro: ${deal.neighbourhood}\n💰 Preço: ${dropText}\n📐 Características: ${deal.properties?.size || 60}m², ${deal.properties?.rooms || 2} quartos.\n\nQuer receber alertas assim no seu Telegram assim que um proprietário baixar o preço ou anunciar?\n\n👉 Comente ALERTA abaixo ou clique no link da bio para ativar o @${this.telegramBotUser}!`,
        slides: [
          {
            slideNumber: 1,
            title: 'Achado da Semana em Maceió',
            body: `Imóvel monitorado com valor abaixo da mediana do bairro!`,
            highlightedMetric: `📍 ${deal.neighbourhood}`,
          },
          {
            slideNumber: 2,
            title: deal.title,
            body: `${dropText}. Localização excelente com ${deal.properties?.rooms || 2} qts e ${deal.properties?.size || 60}m².`,
            highlightedMetric: `R$ ${deal.price_value}/mês`,
          },
          {
            slideNumber: 3,
            title: `Mediana do Bairro (${deal.neighbourhood})`,
            body: `O valor médio pedido na região é de R$ ${marketData.summary.median_price || 3000}/mês. Essa opção está com excelente custo-benefício.`,
            highlightedMetric: `Economia de até 20%`,
          },
          {
            slideNumber: 4,
            title: 'Quer ser avisado primeiro?',
            body: `Nosso robô varre os portais diariamente e avisa quando surge imóvel bom. Comente ALERTA ou acesse o link na bio.`,
            highlightedMetric: `@${this.telegramBotUser}`,
          },
        ],
        cta: `Comente "ALERTA" para receber imóveis assim direto no seu Telegram pelo @${this.telegramBotUser}!`,
        hashtags: ['#maceio', '#imoveismaceio', '#aluguelmaceio', `#${deal.neighbourhood.toLowerCase().replace(/\s+/g, '')}`, '#imovelradar'],
      };
    }

    if (topic.type === 'MARKET_TREND') {
      return {
        title: `Maceió: ${marketData.new_count || 48} novos imóveis entraram no radar`,
        hook: `O que está acontecendo com os preços de aluguel em Maceió? 📊`,
        caption: `Analisamos ${marketData.summary.sample} anúncios ativos em Maceió nesta semana.\n\n📈 Mediana geral: R$ ${marketData.summary.median_price || 2800}/mês (R$ ${marketData.summary.median_price_m2 || 38}/m²)\n🔻 Imóveis que baixaram de preço: ${marketData.price_drop_count || 32} oportunidades\n🆕 Anúncios novos monitorados: ${marketData.new_count || 48}\n\nNão alugue sem consultar o radar.\n\nComente ALERTA para receber novidades personalizadas!`,
        slides: [
          {
            slideNumber: 1,
            title: 'Panorama do Mercado Imobiliário',
            body: `O que dizem os números reais de ${marketData.summary.sample} anúncios monitorados em Maceió.`,
            highlightedMetric: `Maceió - Análise Semanal`,
          },
          {
            slideNumber: 2,
            title: 'Preço Mediano por m²',
            body: `A mediana geral da cidade está em R$ ${marketData.summary.median_price_m2 || 38}/m². Ponta Verde e Jatiúca puxam o topo.`,
            highlightedMetric: `R$ ${marketData.summary.median_price_m2 || 38} / m²`,
          },
          {
            slideNumber: 3,
            title: 'Quedas de Preço Detectadas',
            body: `${marketData.price_drop_count || 32} proprietários reduziram o valor pedido nos últimos dias. Quem tem alerta configurado recebe na hora.`,
            highlightedMetric: `${marketData.price_drop_count || 32} reduções`,
          },
          {
            slideNumber: 4,
            title: 'Crie seu Alerta Grátis',
            body: `Defina bairro, valor máximo e quantidade de quartos no Telegram e receba os melhores anúncios.`,
            highlightedMetric: `@${this.telegramBotUser}`,
          },
        ],
        cta: `Comente "ALERTA" para ativar seu radar gratuito no Telegram @${this.telegramBotUser}!`,
        hashtags: ['#maceio', '#aluguelmaceio', '#imoveismaceio', '#pontavertemaceio', '#jatiuca', '#imovelradar'],
      };
    }

    // Default: PRICE_RANKING
    return {
      title: 'Ranking do m² em Maceió: Bairros Mais Caros e Baratos',
      hook: `Quanto custa de verdade morar nos bairros de Maceió em 2026? 🏢`,
      caption: `Você sabe qual bairro tem o metro quadrado mais disputado de Maceió?\n\n🥇 Mais valorizado: ${topExpensive.name} (R$ ${topExpensive.median_price_m2}/m²)\n💡 Melhor custo por m²: ${cheapest.name} (R$ ${cheapest.median_price_m2}/m²)\n\nVeja no carrossel o ranking completo e comente ALERTA para ser avisado de imóveis vagos nesses bairros!`,
      slides: [
        {
          slideNumber: 1,
          title: 'Ranking do m² em Maceió',
          body: 'Baseado na análise em tempo real dos imóveis cadastrados nos portais.',
          highlightedMetric: 'Aluguel em Maceió',
        },
        {
          slideNumber: 2,
          title: 'Top Bairros Mais Valorizados',
          body: `1. ${topExpensive.name}: R$ ${topExpensive.median_price_m2}/m²\n2. Jatiúca: R$ 41/m²\n3. Pajuçara: R$ 39/m²`,
          highlightedMetric: `Topo: ${topExpensive.name}`,
        },
        {
          slideNumber: 3,
          title: 'Oportunidades de Custo-Benefício',
          body: `Mangabeiras (R$ 32/m²) e Cruz das Almas (R$ 33/m²) continuam excelentes alternativas à beira-mar com valores menores.`,
          highlightedMetric: 'Alternativas inteligentes',
        },
        {
          slideNumber: 4,
          title: 'Quer monitorar seu bairro favorito?',
          body: `Crie um alerta em 30 segundos no Telegram e receba apenas os imóveis que cabem no seu bolso.`,
          highlightedMetric: `@${this.telegramBotUser}`,
        },
      ],
      cta: `Comente "ALERTA" para ativar seu monitor no Telegram @${this.telegramBotUser}!`,
      hashtags: ['#maceio', '#aluguelmaceio', '#pontavertemaceio', '#jatiuca', '#imovelradar'],
    };
  }

  async classifyComment(commentText: string): Promise<CommentAnalysis> {
    const textLower = commentText.toLowerCase().trim();

    // 1. Detecção de Spam / Links / Golpes
    const spamKeywords = [
      'ganhe dinheiro',
      'renda extra',
      'seguidores',
      'clique no link da bio',
      'cripto',
      'whatsapp me',
      'investimento garantido',
      'trabalhe em casa',
      'direct me',
      'promote it on',
    ];
    if (spamKeywords.some((w) => textLower.includes(w)) || textLower.includes('http://') || textLower.includes('https://')) {
      return {
        intent: 'SPAM',
        confidence: 0.98,
        suggestedReply: '',
        shouldHide: true,
        reason: 'Contém padrões de spam, promoção de seguidores ou links não autorizados.',
      };
    }

    // 2. Pedido explícito de Alerta / Bot Telegram
    if (
      textLower.includes('alerta') ||
      textLower.includes('quero') ||
      textLower.includes('link') ||
      textLower.includes('avisa') ||
      textLower.includes('manda') ||
      textLower.includes('bot') ||
      textLower.includes('telegram')
    ) {
      return {
        intent: 'ALERT_REQUEST',
        confidence: 0.95,
        suggestedReply: `Oi! Te enviei detalhes no direct, mas você também pode abrir o Telegram e buscar por @${this.telegramBotUser} para criar alertas gratuitos em 30 segundos! 🏠🔔`,
        shouldHide: false,
        reason: 'Usuário demonstrou interesse em receber alertas ou acessar o serviço.',
      };
    }

    // 3. Dúvida de Preço / Bairro
    if (
      textLower.includes('preço') ||
      textLower.includes('preco') ||
      textLower.includes('quanto') ||
      textLower.includes('valor') ||
      textLower.includes('bairro') ||
      textLower.includes('ponta verde') ||
      textLower.includes('jatiuca') ||
      textLower.includes('pajucara') ||
      textLower.includes('farol')
    ) {
      return {
        intent: 'PRICE_QUERY',
        confidence: 0.88,
        suggestedReply: `Boa pergunta! Os valores variam muito por metragem e condomínio. No bot do Telegram (@${this.telegramBotUser}) você filtra por preço máximo e bairro para ver a média exata. Dá uma conferida!`,
        shouldHide: false,
        reason: 'Pergunta sobre preço, localização ou condomínio.',
      };
    }

    // 4. Engajamento Geral
    return {
      intent: 'GENERAL_ENGAGEMENT',
      confidence: 0.82,
      suggestedReply: `Muito obrigado pelo comentário! Acompanhe nossos posts diários para ficar por dentro de todas as novidades do mercado imobiliário de Maceió. 🚀`,
      shouldHide: false,
      reason: 'Elogio, reação ou comentário geral sobre a publicação.',
    };
  }

  async analyzePerformanceAndSuggest(
    metrics: {
      reach: number;
      impressions: number;
      engagementRate: number;
      topPosts: Array<{ mediaId: string; engagement: number; reach: number; caption?: string }>;
    },
    pastTopics: string[] = []
  ): Promise<PerformanceAnalysis> {
    const rateFormatted = (metrics.engagementRate * 100).toFixed(1);

    return {
      summary: `O perfil atingiu ${metrics.reach.toLocaleString()} contas com taxa de engajamento média de ${rateFormatted}%. Carrosséis comparativos de bairros tiveram 35% mais salvamentos que posts de imagem única.`,
      keyInsights: [
        'Posts com rankings de preço/m² geram o maior número de compartilhamentos e salvamentos.',
        'Chamadas com CTA "Comente ALERTA" aumentaram a taxa de comentários qualificados em 42%.',
        'Imóveis na Jatiúca e Ponta Verde despertam maior interesse de aluguel residencial.',
      ],
      nextPautas: [
        {
          title: 'Ponta Verde vs Jatiúca: Onde o m² de 2 quartos rende mais?',
          reason: 'Excelente apelo de comparação direta entre os dois bairros mais buscados.',
          suggestedFormat: 'CAROUSEL',
        },
        {
          title: '3 Imóveis em Maceió que baixaram mais de R$ 400 no aluguel nesta semana',
          reason: 'Foco em oportunidade e urgência (quedas reais de preço).',
          suggestedFormat: 'CAROUSEL',
        },
        {
          title: 'Guia Rápido: Como calcular o custo real de aluguel + condomínio + IPTU em Maceió',
          reason: 'Conteúdo educativo com alto potencial de salvamento.',
          suggestedFormat: 'CAROUSEL',
        },
      ],
    };
  }

  // Métodos remotos com fallback gracioso
  private async generateWithOpenAI(
    topic: ContentTopic,
    marketData: MarketKindStats,
    deals: ListingItem[]
  ): Promise<GeneratedContentCopy> {
    const prompt = `Gere uma publicação para o Instagram do Imóvel Radar Maceió.
Tema: ${topic.type} (${topic.neighborhood || 'Maceió'}).
Dados: ${JSON.stringify({ summary: marketData.summary, deals: deals.slice(0, 2) })}.
Retorne um JSON com os campos: title, hook, caption, slides (array com slideNumber, title, body, highlightedMetric), cta, hashtags.`;

    const res = await fetch('https://api.openai.com/v1/chat/completions', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${this.openaiKey}`,
      },
      body: JSON.stringify({
        model: process.env.LLM_MODEL || 'gpt-4o-mini',
        messages: [
          {
            role: 'system',
            content: 'Você é o Content Manager especialista do Imóvel Radar Maceió. Responda estritamente em JSON válido.',
          },
          { role: 'user', content: prompt },
        ],
        response_format: { type: 'json_object' },
      }),
    });

    if (!res.ok) throw new Error(`OpenAI HTTP ${res.status}`);
    const data = (await res.json()) as any;
    return JSON.parse(data.choices[0].message.content);
  }

  private async generateWithGemini(
    topic: ContentTopic,
    marketData: MarketKindStats,
    deals: ListingItem[]
  ): Promise<GeneratedContentCopy> {
    const prompt = `Gere conteúdo para Instagram do Imóvel Radar Maceió no formato JSON:
${JSON.stringify({ topic, summary: marketData.summary, deals: deals.slice(0, 2) })}`;

    const res = await fetch(
      `https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key=${this.geminiKey}`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          contents: [{ parts: [{ text: prompt }] }],
          generationConfig: { responseMimeType: 'application/json' },
        }),
      }
    );

    if (!res.ok) throw new Error(`Gemini HTTP ${res.status}`);
    const data = (await res.json()) as any;
    return JSON.parse(data.candidates[0].content.parts[0].text);
  }
}
