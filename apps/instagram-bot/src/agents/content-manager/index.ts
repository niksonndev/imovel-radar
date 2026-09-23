import { DatabaseClient, InstagramPostRecord } from '../../infrastructure/database/client.js';
import { LLMService, ContentTopic } from '../../infrastructure/ai/llm-service.js';
import { CardGenerator } from '../../infrastructure/renderer/card-generator.js';
import { InstagramClient, PublishResult } from '../../infrastructure/instagram/types.js';

export interface ContentManagerOptions {
  db: DatabaseClient;
  llm: LLMService;
  cardGenerator: CardGenerator;
  instagramClient: InstagramClient;
  publicAssetBaseUrl?: string;
}

export class ContentManagerAgent {
  private db: DatabaseClient;
  private llm: LLMService;
  private cardGenerator: CardGenerator;
  private instagramClient: InstagramClient;
  private publicAssetBaseUrl: string;

  constructor(options: ContentManagerOptions) {
    this.db = options.db;
    this.llm = options.llm;
    this.cardGenerator = options.cardGenerator;
    this.instagramClient = options.instagramClient;
    this.publicAssetBaseUrl =
      options.publicAssetBaseUrl ||
      process.env.SITE_BASE_URL ||
      'https://imovelradar.com.br';
  }

  /**
   * Analisa os dados de mercado e gera uma nova pauta com copy e slides visuais.
   */
  async generatePost(topicOverride?: ContentTopic): Promise<InstagramPostRecord> {
    const snapshot = await this.db.getLatestMarketSnapshot('maceio');
    const rentalData = snapshot?.payload?.maceio?.rental;

    if (!rentalData) {
      throw new Error('Dados de mercado não encontrados para gerar conteúdo.');
    }

    const deals = await this.db.getTopDeals({
      municipality: 'Maceió',
      listingKind: 'aluguel',
      limit: 3,
    });

    const topic: ContentTopic = topicOverride || (deals.length > 0 && Math.random() > 0.5
      ? { type: 'OPPORTUNITY_DEAL', neighborhood: deals[0].neighbourhood }
      : { type: 'PRICE_RANKING' });

    // Gera texto e estrutura dos slides com IA
    const copy = await this.llm.generateContentCopy(topic, rentalData, deals);

    const postId = `post_${Date.now()}_${Math.random().toString(36).substring(2, 7)}`;

    // Gera imagens SVG dos slides
    const renderResults = await this.cardGenerator.generateCarouselSlides(
      postId,
      copy.slides
    );

    const fullCaption = `${copy.hook}\n\n${copy.caption}\n\n${copy.cta}\n\n${copy.hashtags.join(' ')}`;

    const postRecord: InstagramPostRecord = {
      id: postId,
      title: copy.title,
      caption: fullCaption,
      postType: 'CAROUSEL',
      status: 'DRAFT',
      slides: renderResults.map((r, idx) => ({
        slideNumber: r.slideNumber,
        title: copy.slides[idx]?.title || `Slide ${r.slideNumber}`,
        subtitle: copy.slides[idx]?.body,
        svgContent: r.svgContent,
        imageUrl: `${this.publicAssetBaseUrl}/generated/${r.slideNumber}.png`,
      })),
      metadata: {
        topic,
        hashtags: copy.hashtags,
        slideCount: renderResults.length,
      },
      createdAt: new Date(),
    };

    await this.db.savePost(postRecord);
    return postRecord;
  }

  /**
   * Publica imediatamente um post criado no Instagram
   */
  async publishPost(postId: string): Promise<PublishResult> {
    const post = await this.db.getPost(postId);
    if (!post) {
      throw new Error(`Post não encontrado com id: ${postId}`);
    }

    const imageUrls = post.slides.map(
      (s) => s.imageUrl || `${this.publicAssetBaseUrl}/assets/slide_${s.slideNumber}.png`
    );

    let result: PublishResult;
    if (post.postType === 'CAROUSEL' && imageUrls.length > 1) {
      result = await this.instagramClient.publishCarousel(post.caption, imageUrls);
    } else {
      result = await this.instagramClient.publishPost(post.caption, imageUrls[0]);
    }

    await this.db.updatePostStatus(
      postId,
      'PUBLISHED',
      result.mediaId,
      result.publishedAt
    );

    return result;
  }

  /**
   * Agenda um post para publicação futura
   */
  async schedulePost(postId: string, date: Date): Promise<InstagramPostRecord> {
    const post = await this.db.getPost(postId);
    if (!post) {
      throw new Error(`Post não encontrado com id: ${postId}`);
    }

    post.status = 'SCHEDULED';
    post.scheduledFor = date;
    await this.db.savePost(post);
    return post;
  }

  /**
   * Processa a fila de posts agendados que chegaram na data de publicação
   */
  async processQueue(): Promise<Array<{ postId: string; result?: PublishResult; error?: string }>> {
    const scheduled = await this.db.getScheduledPosts();
    const now = new Date();
    const results: Array<{ postId: string; result?: PublishResult; error?: string }> = [];

    for (const post of scheduled) {
      if (post.status === 'APPROVED' || (post.scheduledFor && post.scheduledFor <= now)) {
        try {
          const res = await this.publishPost(post.id);
          results.push({ postId: post.id, result: res });
        } catch (err: any) {
          results.push({ postId: post.id, error: err.message || 'Erro desconhecido' });
        }
      }
    }

    return results;
  }

  async listPosts(status?: InstagramPostRecord['status']): Promise<InstagramPostRecord[]> {
    const all = await this.db.getAllPosts();
    if (!status) return all;
    return all.filter((p) => p.status === status);
  }
}
