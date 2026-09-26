import fs from 'node:fs';
import path from 'node:path';
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

export class MockInstagramClient implements InstagramClient {
  readonly platform = 'instagram' as const;
  readonly capabilities: SocialCapabilities = {
    singleImage: true,
    carousel: true,
    video: true,
    videoFromFile: true,
    replyComment: true,
    hideComment: true,
  };
  private filePath: string;
  private state: MockState;

  constructor(storagePath?: string) {
    this.filePath =
      storagePath ?? path.resolve(process.cwd(), '.mock-instagram-state.json');
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
          id: 'mock_media_101',
          caption:
            'Ranking do m2 em Maceió! Ponta Verde lidera com R$ 9.800/m2. Confira as oportunidades da semana. Comente ALERTA para receber imóveis!',
          mediaType: 'CAROUSEL_ALBUM',
          mediaUrls: ['https://imovelradar.com.br/assets/mock-card-1.png'],
          permalink: 'https://instagram.com/p/mock101',
          timestamp: new Date(Date.now() - 24 * 3600 * 1000).toISOString(),
          likeCount: 42,
          commentsCount: 3,
        },
      ],
      comments: [
        {
          id: 'mock_comment_201',
          mediaId: 'mock_media_101',
          text: 'ALERTA! Quero apê 2 quartos na Ponta Verde até 3k',
          username: 'usuario_maceio',
          timestamp: new Date(Date.now() - 12 * 3600 * 1000).toISOString(),
          hidden: false,
          replies: [],
        },
        {
          id: 'mock_comment_202',
          mediaId: 'mock_media_101',
          text: 'Ganhe 10k seguidores por dia clicando no meu link da bio!!',
          username: 'spam_bot_99',
          timestamp: new Date(Date.now() - 6 * 3600 * 1000).toISOString(),
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
      // Ignora erro em ambientes de leitura restrita
    }
  }

  async publishPost(caption: string, imageUrl: string): Promise<PublishResult> {
    const id = `mock_media_${Date.now()}`;
    const publishedAt = new Date();
    const permalink = `https://instagram.com/p/${id}`;

    this.state.posts.unshift({
      id,
      caption,
      mediaType: 'IMAGE',
      mediaUrls: [imageUrl],
      permalink,
      timestamp: publishedAt.toISOString(),
      likeCount: 0,
      commentsCount: 0,
    });
    this.saveState(this.state);

    return { mediaId: id, permalink, publishedAt };
  }

  async publishCarousel(
    caption: string,
    imageUrls: string[]
  ): Promise<PublishResult> {
    const id = `mock_carousel_${Date.now()}`;
    const publishedAt = new Date();
    const permalink = `https://instagram.com/p/${id}`;

    this.state.posts.unshift({
      id,
      caption,
      mediaType: 'CAROUSEL_ALBUM',
      mediaUrls: imageUrls,
      permalink,
      timestamp: publishedAt.toISOString(),
      likeCount: 0,
      commentsCount: 0,
    });
    this.saveState(this.state);

    return { mediaId: id, permalink, publishedAt };
  }

  async publishVideo(
    caption: string,
    videoUrl: string
  ): Promise<PublishResult> {
    const id = `mock_video_${Date.now()}`;
    const publishedAt = new Date();
    const permalink = `https://instagram.com/reel/${id}`;

    this.state.posts.unshift({
      id,
      caption,
      mediaType: 'VIDEO',
      mediaUrls: [videoUrl],
      permalink,
      timestamp: publishedAt.toISOString(),
      likeCount: 0,
      commentsCount: 0,
    });
    this.saveState(this.state);

    return { mediaId: id, permalink, publishedAt };
  }

  async publishVideoFromFile(
    caption: string,
    filePath: string
  ): Promise<PublishResult> {
    return this.publishVideo(caption, filePath);
  }

  async getRecentMedia(limit = 10): Promise<InstagramMedia[]> {
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

  async getComments(mediaId: string): Promise<InstagramComment[]> {
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
        username: 'webhook_user',
        timestamp: new Date().toISOString(),
        hidden: false,
        replies: [],
      };
      this.state.comments.push(comment);
    }

    const replyId = `mock_reply_${Date.now()}`;
    const createdAt = new Date();

    comment.replies.push({
      id: replyId,
      parentCommentId: commentId,
      text: message,
      createdAt: createdAt.toISOString(),
    });

    // Atualiza contagem de comentários no post correspondente
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
        username: 'webhook_user',
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
    const likes = post ? post.likeCount : 25;
    const comments = post ? post.commentsCount : 5;
    const reach = likes * 10 + 250;
    const impressions = Math.floor(reach * 1.35);
    const saved = Math.max(1, Math.floor(likes * 0.4));
    const shares = Math.max(1, Math.floor(likes * 0.2));
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
      impressions: 4800 * multiplier,
      reach: 3200 * multiplier,
      profileViews: 180 * multiplier,
      followerCount: 1420 + multiplier * 5,
      websiteClicks: 45 * multiplier,
    };
  }

  // Métodos auxiliares para testes e simulações
  addMockComment(mediaId: string, username: string, text: string): InstagramComment {
    const id = `mock_comment_${Date.now()}_${Math.random().toString(36).substring(2, 6)}`;
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
    if (post) {
      post.commentsCount += 1;
    }

    this.saveState(this.state);
    return comment;
  }

  clearState(): void {
    this.state = { posts: [], comments: [] };
    this.saveState(this.state);
  }

  getState(): MockState {
    return this.state;
  }
}
