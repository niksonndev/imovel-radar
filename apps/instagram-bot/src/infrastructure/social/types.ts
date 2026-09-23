export type SocialPlatform = 'instagram' | 'tiktok';

export interface SocialCapabilities {
  singleImage: boolean;
  carousel: boolean;
  video: boolean;
  replyComment: boolean;
  hideComment: boolean;
}

export interface PublishResult {
  mediaId: string;
  permalink?: string;
  publishedAt: Date;
}

export interface SocialMedia {
  id: string;
  caption?: string;
  mediaType: 'IMAGE' | 'CAROUSEL_ALBUM' | 'VIDEO';
  mediaUrl?: string;
  permalink: string;
  timestamp: string;
  likeCount?: number;
  commentsCount?: number;
}

export interface SocialComment {
  id: string;
  mediaId: string;
  text: string;
  username: string;
  timestamp: string;
  hidden?: boolean;
  replies?: SocialComment[];
}

export interface CommentReplyResult {
  replyId: string;
  parentCommentId: string;
  text: string;
  createdAt: Date;
}

export interface MediaInsights {
  mediaId: string;
  reach: number;
  impressions: number;
  saved: number;
  shares: number;
  engagement: number;
  likes: number;
  comments: number;
}

export interface AccountInsights {
  period: 'day' | 'week' | 'days_28';
  impressions: number;
  reach: number;
  profileViews: number;
  followerCount: number;
  websiteClicks?: number;
}

export interface SocialClient {
  readonly platform: SocialPlatform;
  readonly capabilities: SocialCapabilities;

  publishPost(caption: string, imageUrl: string): Promise<PublishResult>;
  publishCarousel(caption: string, imageUrls: string[]): Promise<PublishResult>;
  publishVideo(caption: string, videoUrl: string): Promise<PublishResult>;
  getRecentMedia(limit?: number): Promise<SocialMedia[]>;
  getComments(mediaId: string): Promise<SocialComment[]>;
  replyComment(commentId: string, message: string): Promise<CommentReplyResult>;
  hideComment(commentId: string): Promise<boolean>;
  getMediaInsights(mediaId: string): Promise<MediaInsights>;
  getAccountInsights(period?: 'day' | 'week' | 'days_28'): Promise<AccountInsights>;
}
