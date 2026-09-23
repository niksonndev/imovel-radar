import {
  AccountInsights,
  CommentReplyResult,
  InstagramClient,
  InstagramComment,
  InstagramMedia,
  MediaInsights,
  PublishResult,
  SocialCapabilities,
} from './types.js';

export interface MetaGraphConfig {
  accountId: string;
  accessToken: string;
  apiVersion?: string;
  baseUrl?: string;
}

export class MetaGraphInstagramClient implements InstagramClient {
  readonly platform = 'instagram' as const;
  readonly capabilities: SocialCapabilities = {
    singleImage: true,
    carousel: true,
    video: false,
    replyComment: true,
    hideComment: true,
  };
  private accountId: string;
  private accessToken: string;
  private baseUrl: string;

  constructor(config: MetaGraphConfig) {
    if (!config.accountId || !config.accessToken) {
      throw new Error(
        'MetaGraphInstagramClient requer accountId e accessToken válidos'
      );
    }
    this.accountId = config.accountId;
    this.accessToken = config.accessToken;
    const version = config.apiVersion || 'v21.0';
    this.baseUrl = config.baseUrl || `https://graph.facebook.com/${version}`;
  }

  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    const url = new URL(`${this.baseUrl}${endpoint}`);
    if (!url.searchParams.has('access_token')) {
      url.searchParams.set('access_token', this.accessToken);
    }

    const response = await fetch(url.toString(), {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json',
        ...(options.headers || {}),
      },
    });

    const data = (await response.json()) as any;

    if (!response.ok || data.error) {
      const msg =
        data.error?.message ||
        `Erro na Meta Graph API (${response.status}): ${response.statusText}`;
      throw new Error(`[MetaGraphAPI] ${msg}`);
    }

    return data as T;
  }

  async publishPost(caption: string, imageUrl: string): Promise<PublishResult> {
    // 1. Cria contêiner de imagem
    const container = await this.request<{ id: string }>(
      `/${this.accountId}/media`,
      {
        method: 'POST',
        body: JSON.stringify({
          image_url: imageUrl,
          caption,
        }),
      }
    );

    // 2. Publica o contêiner
    const published = await this.request<{ id: string }>(
      `/${this.accountId}/media_publish`,
      {
        method: 'POST',
        body: JSON.stringify({
          creation_id: container.id,
        }),
      }
    );

    return {
      mediaId: published.id,
      publishedAt: new Date(),
    };
  }

  async publishCarousel(
    caption: string,
    imageUrls: string[]
  ): Promise<PublishResult> {
    if (imageUrls.length < 2) {
      throw new Error('Carrossel requer no mínimo 2 imagens.');
    }

    // 1. Cria cada item filho
    const childIds: string[] = [];
    for (const imgUrl of imageUrls) {
      const child = await this.request<{ id: string }>(
        `/${this.accountId}/media`,
        {
          method: 'POST',
          body: JSON.stringify({
            image_url: imgUrl,
            is_carousel_item: true,
          }),
        }
      );
      childIds.push(child.id);
    }

    // 2. Cria contêiner pai
    const parentContainer = await this.request<{ id: string }>(
      `/${this.accountId}/media`,
      {
        method: 'POST',
        body: JSON.stringify({
          media_type: 'CAROUSEL',
          children: childIds.join(','),
          caption,
        }),
      }
    );

    // 3. Publica contêiner pai
    const published = await this.request<{ id: string }>(
      `/${this.accountId}/media_publish`,
      {
        method: 'POST',
        body: JSON.stringify({
          creation_id: parentContainer.id,
        }),
      }
    );

    return {
      mediaId: published.id,
      publishedAt: new Date(),
    };
  }

  async publishVideo(
    _caption: string,
    _videoUrl: string
  ): Promise<PublishResult> {
    throw new Error(
      'Publicação de vídeo não é suportada no InstagramClient nesta versão.'
    );
  }

  async getRecentMedia(limit = 10): Promise<InstagramMedia[]> {
    const fields =
      'id,caption,media_type,media_url,permalink,timestamp,like_count,comments_count';
    const res = await this.request<{ data: any[] }>(
      `/${this.accountId}/media?fields=${fields}&limit=${limit}`
    );

    return (res.data || []).map((item) => ({
      id: item.id,
      caption: item.caption,
      mediaType: item.media_type,
      mediaUrl: item.media_url,
      permalink: item.permalink,
      timestamp: item.timestamp,
      likeCount: item.like_count ?? 0,
      commentsCount: item.comments_count ?? 0,
    }));
  }

  async getComments(mediaId: string): Promise<InstagramComment[]> {
    const fields = 'id,text,username,timestamp,hidden,replies{id,text,username,timestamp}';
    const res = await this.request<{ data: any[] }>(
      `/${mediaId}/comments?fields=${fields}`
    );

    return (res.data || []).map((c) => ({
      id: c.id,
      mediaId,
      text: c.text,
      username: c.username,
      timestamp: c.timestamp,
      hidden: c.hidden ?? false,
      replies: (c.replies?.data || []).map((r: any) => ({
        id: r.id,
        mediaId,
        text: r.text,
        username: r.username,
        timestamp: r.timestamp,
      })),
    }));
  }

  async replyComment(
    commentId: string,
    message: string
  ): Promise<CommentReplyResult> {
    const res = await this.request<{ id: string }>(`/${commentId}/replies`, {
      method: 'POST',
      body: JSON.stringify({ message }),
    });

    return {
      replyId: res.id,
      parentCommentId: commentId,
      text: message,
      createdAt: new Date(),
    };
  }

  async hideComment(commentId: string): Promise<boolean> {
    const res = await this.request<{ success: boolean }>(`/${commentId}`, {
      method: 'POST',
      body: JSON.stringify({ hide: true }),
    });
    return res.success ?? true;
  }

  async getMediaInsights(mediaId: string): Promise<MediaInsights> {
    try {
      const res = await this.request<{ data: Array<{ name: string; values: Array<{ value: number }> }> }>(
        `/${mediaId}/insights?metric=reach,impressions,saved,shares,total_interactions`
      );

      const metricMap: Record<string, number> = {};
      for (const item of res.data || []) {
        metricMap[item.name] = item.values?.[0]?.value ?? 0;
      }

      return {
        mediaId,
        reach: metricMap.reach ?? 0,
        impressions: metricMap.impressions ?? 0,
        saved: metricMap.saved ?? 0,
        shares: metricMap.shares ?? 0,
        engagement: metricMap.total_interactions ?? 0,
        likes: 0,
        comments: 0,
      };
    } catch {
      // Fallback em caso de métricas parciais ou nova mídia
      return {
        mediaId,
        reach: 0,
        impressions: 0,
        saved: 0,
        shares: 0,
        engagement: 0,
        likes: 0,
        comments: 0,
      };
    }
  }

  async getAccountInsights(
    period: 'day' | 'week' | 'days_28' = 'week'
  ): Promise<AccountInsights> {
    try {
      const res = await this.request<{ data: Array<{ name: string; values: Array<{ value: number }> }> }>(
        `/${this.accountId}/insights?metric=impressions,reach,profile_views&period=${period}`
      );

      const metricMap: Record<string, number> = {};
      for (const item of res.data || []) {
        metricMap[item.name] = item.values?.[0]?.value ?? 0;
      }

      return {
        period,
        impressions: metricMap.impressions ?? 0,
        reach: metricMap.reach ?? 0,
        profileViews: metricMap.profile_views ?? 0,
        followerCount: 0,
      };
    } catch {
      return {
        period,
        impressions: 0,
        reach: 0,
        profileViews: 0,
        followerCount: 0,
      };
    }
  }
}
