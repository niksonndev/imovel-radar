import {
  DEFAULT_GRAPH_API_HOST,
  DEFAULT_GRAPH_API_VERSION,
} from './constants.js';
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
import { readFileSync, statSync } from 'node:fs';

export interface MetaGraphConfig {
  accountId: string;
  accessToken: string;
  apiVersion?: string;
  /** graph.facebook.com (Facebook Login) ou graph.instagram.com (Instagram Login). */
  apiHost?: string;
  baseUrl?: string;
  statusPollMs?: number;
  containerTimeoutMs?: number;
}

type GraphErrorBody = {
  error?: { message?: string; code?: number; error_subcode?: number };
};

export class MetaGraphInstagramClient implements InstagramClient {
  readonly platform = 'instagram' as const;
  readonly capabilities: SocialCapabilities;
  private accountId: string;
  private accessToken: string;
  private apiVersion: string;
  private apiHost: string;
  private baseUrl: string;
  private statusPollMs: number;
  private containerTimeoutMs: number;

  constructor(config: MetaGraphConfig) {
    if (!config.accountId || !config.accessToken) {
      throw new Error(
        'MetaGraphInstagramClient requer accountId e accessToken válidos'
      );
    }
    this.accountId = config.accountId;
    this.accessToken = config.accessToken;
    this.apiVersion = config.apiVersion || DEFAULT_GRAPH_API_VERSION;
    this.apiHost = (config.apiHost || DEFAULT_GRAPH_API_HOST).replace(
      /^https?:\/\//,
      ''
    );
    this.baseUrl = config.baseUrl || `https://${this.apiHost}/${this.apiVersion}`;
    this.statusPollMs = config.statusPollMs ?? 2000;
    this.containerTimeoutMs = config.containerTimeoutMs ?? 90_000;
    const facebookLogin = this.apiHost.includes('graph.facebook.com');
    this.capabilities = {
      singleImage: true,
      carousel: true,
      video: true,
      videoFromFile: facebookLogin,
      replyComment: true,
      hideComment: true,
    };
  }

  private async request<T>(
    endpoint: string,
    options: {
      method?: 'GET' | 'POST';
      params?: Record<string, string | undefined>;
    } = {}
  ): Promise<T> {
    const method = options.method ?? 'GET';
    const url = new URL(
      `${this.baseUrl}${endpoint.startsWith('/') ? endpoint : `/${endpoint}`}`
    );
    const params = options.params ?? {};

    let response: Response;
    if (method === 'GET') {
      url.searchParams.set('access_token', this.accessToken);
      for (const [key, value] of Object.entries(params)) {
        if (value != null && value !== '') url.searchParams.set(key, value);
      }
      response = await fetch(url);
    } else {
      const body = new URLSearchParams();
      body.set('access_token', this.accessToken);
      for (const [key, value] of Object.entries(params)) {
        if (value != null && value !== '') body.set(key, value);
      }
      response = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body,
      });
    }

    const data = (await response.json()) as T & GraphErrorBody;
    if (!response.ok || data.error) {
      const msg =
        data.error?.message ||
        `Erro na Meta Graph API (${response.status}): ${response.statusText}`;
      throw new Error(`[MetaGraphAPI] ${msg}`);
    }
    return data;
  }

  async waitUntilContainerReady(creationId: string): Promise<void> {
    const deadline = Date.now() + this.containerTimeoutMs;
    while (Date.now() < deadline) {
      const status = await this.request<{ status_code?: string }>(
        `/${creationId}`,
        { params: { fields: 'status_code' } }
      );
      const code = status.status_code;
      if (code === 'FINISHED' || code === 'PUBLISHED') return;
      if (code === 'ERROR' || code === 'EXPIRED') {
        throw new Error(
          `[MetaGraphAPI] Contêiner ${creationId} falhou (${code})`
        );
      }
      await new Promise((resolve) => setTimeout(resolve, this.statusPollMs));
    }
    throw new Error(
      `[MetaGraphAPI] Timeout aguardando contêiner ${creationId}`
    );
  }

  private async publishContainer(creationId: string): Promise<PublishResult> {
    await this.waitUntilContainerReady(creationId);
    const published = await this.request<{ id: string }>(
      `/${this.accountId}/media_publish`,
      { method: 'POST', params: { creation_id: creationId } }
    );
    return {
      mediaId: published.id,
      publishedAt: new Date(),
    };
  }

  async publishPost(caption: string, imageUrl: string): Promise<PublishResult> {
    const container = await this.request<{ id: string }>(
      `/${this.accountId}/media`,
      {
        method: 'POST',
        params: { image_url: imageUrl, caption },
      }
    );
    return this.publishContainer(container.id);
  }

  async publishCarousel(
    caption: string,
    imageUrls: string[]
  ): Promise<PublishResult> {
    if (imageUrls.length < 2) {
      throw new Error('Carrossel requer no mínimo 2 imagens.');
    }

    const childIds: string[] = [];
    for (const imgUrl of imageUrls) {
      const child = await this.request<{ id: string }>(
        `/${this.accountId}/media`,
        {
          method: 'POST',
          params: { image_url: imgUrl, is_carousel_item: 'true' },
        }
      );
      await this.waitUntilContainerReady(child.id);
      childIds.push(child.id);
    }

    const parentContainer = await this.request<{ id: string }>(
      `/${this.accountId}/media`,
      {
        method: 'POST',
        params: {
          media_type: 'CAROUSEL',
          children: childIds.join(','),
          caption,
        },
      }
    );

    return this.publishContainer(parentContainer.id);
  }

  async publishVideo(caption: string, videoUrl: string): Promise<PublishResult> {
    const container = await this.request<{ id: string }>(
      `/${this.accountId}/media`,
      {
        method: 'POST',
        params: {
          media_type: 'REELS',
          video_url: videoUrl,
          caption,
          share_to_feed: 'true',
        },
      }
    );
    return this.publishContainer(container.id);
  }

  async publishVideoFromFile(
    caption: string,
    filePath: string
  ): Promise<PublishResult> {
    if (!this.capabilities.videoFromFile) {
      throw new Error(
        'Upload local de Reels exige Facebook Login (GRAPH_API_HOST=graph.facebook.com). Com Instagram Login, use um túnel HTTPS ou --url.'
      );
    }

    const fileSize = statSync(filePath).size;
    const fileBuffer = readFileSync(filePath);

    const container = await this.request<{ id: string; uri?: string }>(
      `/${this.accountId}/media`,
      {
        method: 'POST',
        params: {
          media_type: 'REELS',
          upload_type: 'resumable',
          caption,
          share_to_feed: 'true',
        },
      }
    );

    const uploadUri =
      container.uri ||
      `https://rupload.facebook.com/ig-api-upload/${this.apiVersion}/${container.id}`;

    const uploadRes = await fetch(uploadUri, {
      method: 'POST',
      headers: {
        Authorization: `OAuth ${this.accessToken}`,
        offset: '0',
        file_size: String(fileSize),
      },
      body: fileBuffer,
    });

    const uploadBody = (await uploadRes.json().catch(() => ({}))) as GraphErrorBody;
    if (!uploadRes.ok || uploadBody.error) {
      const msg =
        uploadBody.error?.message ||
        `Falha no rupload (${uploadRes.status})`;
      throw new Error(`[MetaGraphAPI] ${msg}`);
    }

    return this.publishContainer(container.id);
  }

  async getRecentMedia(limit = 10): Promise<InstagramMedia[]> {
    const fields =
      'id,caption,media_type,media_url,permalink,timestamp,like_count,comments_count';
    const res = await this.request<{ data: Array<Record<string, unknown>> }>(
      `/${this.accountId}/media`,
      { params: { fields, limit: String(limit) } }
    );

    return (res.data || []).map((item) => ({
      id: String(item.id),
      caption: item.caption as string | undefined,
      mediaType: item.media_type as InstagramMedia['mediaType'],
      mediaUrl: item.media_url as string | undefined,
      permalink: String(item.permalink ?? ''),
      timestamp: String(item.timestamp ?? ''),
      likeCount: Number(item.like_count ?? 0),
      commentsCount: Number(item.comments_count ?? 0),
    }));
  }

  async getComments(mediaId: string): Promise<InstagramComment[]> {
    const fields =
      'id,text,username,timestamp,hidden,replies{id,text,username,timestamp}';
    const res = await this.request<{ data: Array<Record<string, any>> }>(
      `/${mediaId}/comments`,
      { params: { fields } }
    );

    return (res.data || []).map((c) => ({
      id: c.id,
      mediaId,
      text: c.text,
      username: c.username,
      timestamp: c.timestamp,
      hidden: c.hidden ?? false,
      replies: (c.replies?.data || []).map((r: Record<string, any>) => ({
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
      params: { message },
    });

    return {
      replyId: res.id,
      parentCommentId: commentId,
      text: message,
      createdAt: new Date(),
    };
  }

  async hideComment(commentId: string): Promise<boolean> {
    const res = await this.request<{ success?: boolean }>(`/${commentId}`, {
      method: 'POST',
      params: { hide: 'true' },
    });
    return res.success ?? true;
  }

  private metricValue(
    data: Array<{ name: string; values?: Array<{ value: number }> }>,
    ...names: string[]
  ): number {
    for (const name of names) {
      const item = data.find((row) => row.name === name);
      const value = item?.values?.[0]?.value;
      if (typeof value === 'number') return value;
    }
    return 0;
  }

  async getMediaInsights(mediaId: string): Promise<MediaInsights> {
    const empty: MediaInsights = {
      mediaId,
      reach: 0,
      impressions: 0,
      saved: 0,
      shares: 0,
      engagement: 0,
      likes: 0,
      comments: 0,
    };
    const attempts = [
      'reach,views,saved,shares,total_interactions,likes,comments',
      'reach,impressions,saved,shares,total_interactions',
      'reach,impressions,engagement',
    ];
    for (const metric of attempts) {
      try {
        const res = await this.request<{
          data: Array<{ name: string; values: Array<{ value: number }> }>;
        }>(`/${mediaId}/insights`, { params: { metric } });
        const rows = res.data || [];
        const views = this.metricValue(rows, 'views', 'impressions');
        return {
          mediaId,
          reach: this.metricValue(rows, 'reach'),
          impressions: views,
          saved: this.metricValue(rows, 'saved'),
          shares: this.metricValue(rows, 'shares'),
          engagement: this.metricValue(
            rows,
            'total_interactions',
            'engagement'
          ),
          likes: this.metricValue(rows, 'likes'),
          comments: this.metricValue(rows, 'comments'),
        };
      } catch {
        continue;
      }
    }
    return empty;
  }

  async getAccountInsights(
    period: 'day' | 'week' | 'days_28' = 'day'
  ): Promise<AccountInsights> {
    const empty: AccountInsights = {
      period,
      impressions: 0,
      reach: 0,
      profileViews: 0,
      followerCount: 0,
    };

    let followerCount = 0;
    try {
      const user = await this.request<{ followers_count?: number }>(
        `/${this.accountId}`,
        { params: { fields: 'followers_count' } }
      );
      followerCount = user.followers_count ?? 0;
    } catch {
      followerCount = 0;
    }

    const attempts: Array<{ metric: string; period: string }> = [
      { metric: 'reach,views,accounts_engaged', period: 'day' },
      { metric: 'impressions,reach,profile_views', period },
      { metric: 'impressions,reach,profile_views', period: 'day' },
    ];

    for (const attempt of attempts) {
      try {
        const res = await this.request<{
          data: Array<{ name: string; values: Array<{ value: number }> }>;
        }>(`/${this.accountId}/insights`, {
          params: { metric: attempt.metric, period: attempt.period },
        });
        const rows = res.data || [];
        const views = this.metricValue(rows, 'views', 'impressions');
        return {
          period,
          impressions: views,
          reach: this.metricValue(rows, 'reach'),
          profileViews: this.metricValue(
            rows,
            'profile_views',
            'accounts_engaged'
          ),
          followerCount,
        };
      } catch {
        continue;
      }
    }

    return { ...empty, followerCount };
  }
}
