import { DatabaseClient, InstagramPostRecord } from '../../infrastructure/database/client.js';
import { LLMService, ContentTopic } from '../../infrastructure/ai/llm-service.js';
import { CardGenerator } from '../../infrastructure/renderer/card-generator.js';
import { VideoSlideshowGenerator } from '../../infrastructure/renderer/video-slideshow.js';
import { SocialClient, PublishResult, SocialPlatform } from '../../infrastructure/social/types.js';

export interface ContentManagerOptions {
  db: DatabaseClient;
  llm: LLMService;
  cardGenerator: CardGenerator;
  videoGenerator?: VideoSlideshowGenerator;
  instagramClient?: SocialClient;
  socialClient?: SocialClient;
  publicAssetBaseUrl?: string;
}

export interface GeneratePostOptions {
  topicOverride?: ContentTopic;
  platform?: SocialPlatform;
  format?: 'photo' | 'video';
}

export class ContentManagerAgent {
  private db: DatabaseClient;
  private llm: LLMService;
  private cardGenerator: CardGenerator;
  private videoGenerator: VideoSlideshowGenerator;
  private socialClient: SocialClient;
  private publicAssetBaseUrl: string;

  constructor(options: ContentManagerOptions) {
    this.db = options.db;
    this.llm = options.llm;
    this.cardGenerator = options.cardGenerator;
    this.videoGenerator = options.videoGenerator || new VideoSlideshowGenerator();
    const client = options.socialClient || options.instagramClient;
    if (!client) {
      throw new Error('ContentManagerAgent requer socialClient ou instagramClient');
    }
    this.socialClient = client;
    this.publicAssetBaseUrl =
      options.publicAssetBaseUrl ||
      process.env.SITE_BASE_URL ||
      'https://imovelradar.com.br';
  }

  get instagramClient(): SocialClient {
    return this.socialClient;
  }

  /**
   * Analisa os dados de mercado e gera uma nova pauta com copy e slides visuais.
   */
  async generatePost(
    optionsOrTopic?: ContentTopic | GeneratePostOptions
  ): Promise<InstagramPostRecord> {
    let topicOverride: ContentTopic | undefined;
    let platform: SocialPlatform = this.socialClient.platform;
    let format: 'photo' | 'video' = 'photo';

    if (optionsOrTopic) {
      if ('platform' in optionsOrTopic || 'format' in optionsOrTopic || 'topicOverride' in optionsOrTopic) {
        const opts = optionsOrTopic as GeneratePostOptions & { type?: ContentTopic['type'] };
        if (opts.platform) platform = opts.platform;
        if (opts.format) format = opts.format;
        topicOverride = opts.topicOverride || (opts.type ? ({ type: opts.type } as ContentTopic) : undefined);
      } else if ('type' in optionsOrTopic) {
        topicOverride = optionsOrTopic as ContentTopic;
      }
    }

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

    // Gera texto e estrutura dos slides com IA considerando plataforma e formato
    const copy = await this.llm.generateContentCopy(topic, rentalData, deals, {
      platform,
      format,
    });

    const postId = `post_${Date.now()}_${Math.random().toString(36).substring(2, 7)}`;

    // Gera imagens SVG dos slides com preset de dimensões e copy
    const renderResults = await this.cardGenerator.generateCarouselSlides(
      postId,
      copy.slides,
      platform
    );

    const fullCaption = `${copy.hook}\n\n${copy.caption}\n\n${copy.cta}\n\n${copy.hashtags.join(' ')}`;
    const postType = format === 'video' ? 'VIDEO' : 'CAROUSEL';
    let videoUrl: string | undefined;

    if (format === 'video') {
      const pngPaths = renderResults.map((r) => r.pngPath).filter(Boolean) as string[];
      if (pngPaths.length > 0 && this.videoGenerator.isFfmpegAvailable()) {
        try {
          videoUrl = await this.videoGenerator.createSlideshow(postId, pngPaths);
        } catch (err: any) {
          console.warn('[ContentManager] Falha ao gerar vídeo mp4 com ffmpeg:', err.message);
        }
      }
    }

    const postRecord: InstagramPostRecord = {
      id: postId,
      platform,
      title: copy.title,
      caption: fullCaption,
      postType,
      status: 'DRAFT',
      videoUrl,
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
        format,
      },
      createdAt: new Date(),
    };

    await this.db.savePost(postRecord);
    return postRecord;
  }

  /**
   * Publica imediatamente um post criado
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
    if (post.postType === 'VIDEO') {
      const videoTarget = post.videoUrl || imageUrls[0];
      result = await this.socialClient.publishVideo(post.caption, videoTarget);
    } else if (post.postType === 'CAROUSEL' && imageUrls.length > 1) {
      result = await this.socialClient.publishCarousel(post.caption, imageUrls);
    } else {
      result = await this.socialClient.publishPost(post.caption, imageUrls[0]);
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

  async listPosts(
    status?: InstagramPostRecord['status'],
    platform?: SocialPlatform
  ): Promise<InstagramPostRecord[]> {
    const all = await this.db.getAllPosts(platform);
    if (!status) return all;
    return all.filter((p) => p.status === status);
  }
}
