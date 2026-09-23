import fs from 'node:fs';
import path from 'node:path';
import {
  AccountInsights,
  CommentReplyResult,
  MediaInsights,
  PublishResult,
  SocialCapabilities,
  TikTokClient,
  TikTokComment,
  TikTokMedia,
} from './types.js';

interface MockState {
  posts: Array<{
    id: string;
    caption: string;
    mediaType: 'IMAGE' | 'CAROUSEL_ALBUM' | 'VIDEO';
    mediaUrls: string[];
    permalink: string;
    timestamp: string;
    likeCount: number;
    commentsCount: number;
    shareCount: number;
    viewCount: number;
  }>;
  comments: Array<{
    id: string;
    mediaId: string;
    text: string;
    username: string;
    timestamp: string;
    hidden: boolean;
    replies: Array<{
      id: string;
      parentCommentId: string;
      text: string;
      createdAt: string;
    }>;
  }>;
}

export class MockTikTokClient implements TikTokClient {
  readonly platform = 'tiktok' as const;
  readonly capabilities: SocialCapabilities = {
    singleImage: true,
    carousel: true,
    video: true,
    replyComment: true,
    hideComment: true,
  };

  private filePath: string;
  private state: MockState;

  constructor(storagePath?: string) {
    this.filePath =
      storagePath ?? path.resolve(process.cwd(), '.mock-tiktok-state.json');
    this.state = this.loadState();
  }

  private loadState(): MockState {
    try {
      if (fs.existsSync(this.filePath)) {
        const raw = fs.readFileSync(this.filePath, 'utf-8');
        return JSON.parse(raw);
      }
    } catch {
      // Falha ao ler arquivo: inicia estado vazio
    }

    const defaultState: MockState = {
      posts: [
        {
          id: 'mock_tiktok_101',
          caption:
            'Descubra o valor do m² em Maceió! Ponta Verde e Jatiúca em destaque. Comente ALERTA para receber imóveis selecionados no Telegram! #maceio #imoveis #aluguel',
          mediaType: 'CAROUSEL_ALBUM',
          mediaUrls: ['https://imovelradar.com.br/assets/mock-card-1.png'],
          permalink: 'https://www.tiktok.com/@imovelradar/photo/mock_tiktok_101',
          timestamp: new Date(Date.now() - 24 * 3600 * 1000).toISOString(),
          likeCount: 94,
          commentsCount: 6,
          shareCount: 18,
          viewCount: 1840,
        },
      ],
      comments: [
        {
          id: 'mock_tt_comment_201',
          mediaId: 'mock_tiktok_101',
          text: 'ALERTA! Quero apê 2 quartos na Ponta Verde até 3k',
          username: 'usuario_maceio_tt',
          timestamp: new Date(Date.now() - 20 * 3600 * 1000).toISOString(),
          hidden: false,
          replies: [],
        },
        {
          id: 'mock_tt_comment_202',
          mediaId: 'mock_tiktok_101',
          text: 'Ganhe R$ 800 por dia com renda extra no link da bio bit.ly/spam-tt',
          username: 'bot_spam_tt',
          timestamp: new Date(Date.now() - 15 * 3600 * 1000).toISOString(),
          hidden: false,
          replies: [],
        },
      ],
    };

    this.saveState(defaultState);
    return defaultState;
  }

  private saveState(state: MockState): void {
    try {
      fs.writeFileSync(this.filePath, JSON.stringify(state, null, 2), 'utf-8');
    } catch {
      // Ignora erro em ambientes restritos
    }
  }

  async publishPost(caption: string, imageUrl: string): Promise<PublishResult> {
    const id = `mock_tt_photo_${Date.now()}`;
    const publishedAt = new Date();
    const permalink = `https://www.tiktok.com/@imovelradar/photo/${id}`;

    this.state.posts.unshift({
      id,
      caption,
      mediaType: 'IMAGE',
      mediaUrls: [imageUrl],
      permalink,
      timestamp: publishedAt.toISOString(),
      likeCount: 0,
      commentsCount: 0,
      shareCount: 0,
      viewCount: 0,
    });
    this.saveState(this.state);

    return { mediaId: id, permalink, publishedAt };
  }

  async publishCarousel(
    caption: string,
    imageUrls: string[]
  ): Promise<PublishResult> {
    const id = `mock_tt_carousel_${Date.now()}`;
    const publishedAt = new Date();
    const permalink = `https://www.tiktok.com/@imovelradar/photo/${id}`;

    this.state.posts.unshift({
      id,
      caption,
      mediaType: 'CAROUSEL_ALBUM',
      mediaUrls: imageUrls,
      permalink,
      timestamp: publishedAt.toISOString(),
      likeCount: 0,
      commentsCount: 0,
      shareCount: 0,
      viewCount: 0,
    });
    this.saveState(this.state);

    return { mediaId: id, permalink, publishedAt };
  }

  async publishVideo(
    caption: string,
    videoUrl: string
  ): Promise<PublishResult> {
    const id = `mock_tt_video_${Date.now()}`;
    const publishedAt = new Date();
    const permalink = `https://www.tiktok.com/@imovelradar/video/${id}`;

    this.state.posts.unshift({
      id,
      caption,
      mediaType: 'VIDEO',
      mediaUrls: [videoUrl],
      permalink,
      timestamp: publishedAt.toISOString(),
      likeCount: 0,
      commentsCount: 0,
      shareCount: 0,
      viewCount: 0,
    });
    this.saveState(this.state);

    return { mediaId: id, permalink, publishedAt };
  }

  async getRecentMedia(limit = 10): Promise<TikTokMedia[]> {
    return this.state.posts.slice(0, limit).map((p) => ({
      id: p.id,
      caption: p.caption,
      mediaType: p.mediaType,
      mediaUrl: p.mediaUrls[0],
      permalink: p.permalink,
      timestamp: p.timestamp,
      likeCount: p.likeCount,
      commentsCount: p.commentsCount,
    }));
  }

  async getComments(mediaId: string): Promise<TikTokComment[]> {
    return this.state.comments
      .filter((c) => c.mediaId === mediaId)
      .map((c) => ({
        id: c.id,
        mediaId: c.mediaId,
        text: c.text,
        username: c.username,
        timestamp: c.timestamp,
        hidden: c.hidden,
        replies: c.replies.map((r) => ({
          id: r.id,
          mediaId: c.mediaId,
          text: r.text,
          username: 'imovelradar',
          timestamp: r.createdAt,
        })),
      }));
  }

  async replyComment(
    commentId: string,
    message: string
  ): Promise<CommentReplyResult> {
    let comment = this.state.comments.find((c) => c.id === commentId);
    if (!comment) {
      comment = {
        id: commentId,
        mediaId: 'unknown_media',
        text: '',
        username: 'webhook_user_tt',
        timestamp: new Date().toISOString(),
        hidden: false,
        replies: [],
      };
      this.state.comments.push(comment);
    }

    const replyId = `mock_tt_reply_${Date.now()}`;
    const createdAt = new Date();

    comment.replies.push({
      id: replyId,
      parentCommentId: commentId,
      text: message,
      createdAt: createdAt.toISOString(),
    });

    const post = this.state.posts.find((p) => p.id === comment.mediaId);
    if (post) {
      post.commentsCount += 1;
    }

    this.saveState(this.state);
    return {
      replyId,
      parentCommentId: commentId,
      text: message,
      createdAt,
    };
  }

  async hideComment(commentId: string): Promise<boolean> {
    let comment = this.state.comments.find((c) => c.id === commentId);
    if (!comment) {
      comment = {
        id: commentId,
        mediaId: 'unknown_media',
        text: '',
        username: 'webhook_user_tt',
        timestamp: new Date().toISOString(),
        hidden: true,
        replies: [],
      };
      this.state.comments.push(comment);
      this.saveState(this.state);
      return true;
    }
    comment.hidden = true;
    this.saveState(this.state);
    return true;
  }

  async getMediaInsights(mediaId: string): Promise<MediaInsights> {
    const post = this.state.posts.find((p) => p.id === mediaId);
    const likes = post ? post.likeCount : 40;
    const comments = post ? post.commentsCount : 8;
    const shares = post ? post.shareCount : 12;
    const impressions = post && post.viewCount > 0 ? post.viewCount : likes * 25 + 500;
    const reach = Math.floor(impressions * 0.85);
    const saved = Math.max(1, Math.floor(likes * 0.3));
    const engagement = likes + comments + saved + shares;

    return {
      mediaId,
      reach,
      impressions,
      saved,
      shares,
      engagement,
      likes,
      comments,
    };
  }

  async getAccountInsights(
    period: 'day' | 'week' | 'days_28' = 'week'
  ): Promise<AccountInsights> {
    const multiplier = period === 'day' ? 1 : period === 'week' ? 7 : 28;
    return {
      period,
      impressions: 7200 * multiplier,
      reach: 5100 * multiplier,
      profileViews: 340 * multiplier,
      followerCount: 2850 + multiplier * 12,
      websiteClicks: 65 * multiplier,
    };
  }

  addMockComment(mediaId: string, username: string, text: string): TikTokComment {
    const id = `mock_tt_comment_${Date.now()}_${Math.random().toString(36).substring(2, 6)}`;
    const comment = {
      id,
      mediaId,
      text,
      username,
      timestamp: new Date().toISOString(),
      hidden: false,
      replies: [],
    };
    this.state.comments.push(comment);
    const post = this.state.posts.find((p) => p.id === mediaId);
    if (post) post.commentsCount += 1;
    this.saveState(this.state);
    return comment;
  }

  resetState(): void {
    if (fs.existsSync(this.filePath)) {
      try {
        fs.unlinkSync(this.filePath);
      } catch {
        // Ignora erro
      }
    }
    this.state = this.loadState();
  }
}
