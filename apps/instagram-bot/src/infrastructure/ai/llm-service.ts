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
    suggestedFormat: 'CAROUSEL' | 'SINGLE_IMAGE' | 'VIDEO';
  }>;
}

export class LLMService {
  private telegramBotUser: string;

  constructor() {
    this.telegramBotUser = process.env.TELEGRAM_BOT_USERNAME || 'imovelradar_bot';
  }

  async classifyComment(commentText: string): Promise<CommentAnalysis> {
    const textLower = commentText.toLowerCase().trim();

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
    if (
      spamKeywords.some((w) => textLower.includes(w)) ||
      textLower.includes('http://') ||
      textLower.includes('https://')
    ) {
      return {
        intent: 'SPAM',
        confidence: 0.98,
        suggestedReply: '',
        shouldHide: true,
        reason: 'Contém padrões de spam, promoção de seguidores ou links não autorizados.',
      };
    }

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

    return {
      intent: 'GENERAL_ENGAGEMENT',
      confidence: 0.82,
      suggestedReply: `Muito obrigado pelo comentário! Acompanhe nossos posts diários para ficar por dentro de todas as novidades do mercado imobiliário de Maceió. 🚀`,
      shouldHide: false,
      reason: 'Elogio, reação ou comentário geral sobre a publicação.',
    };
  }

  async analyzePerformanceAndSuggest(metrics: {
    reach: number;
    impressions: number;
    engagementRate: number;
    topPosts: Array<{ mediaId: string; engagement: number; reach: number; caption?: string }>;
  }): Promise<PerformanceAnalysis> {
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
}
