export interface PublishResult {
  mediaId: string;
  permalink?: string;
  publishedAt: Date;
}

export interface InstagramMedia {
  id: string;
  caption?: string;
  mediaType: 'IMAGE' | 'CAROUSEL_ALBUM' | 'VIDEO';
  mediaUrl?: string;
  permalink: string;
  timestamp: string;
  likeCount?: number;
  commentsCount?: number;
}

export interface InstagramComment {
  id: string;
  mediaId: string;
  text: string;
  username: string;
  timestamp: string;
  hidden?: boolean;
  replies?: InstagramComment[];
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

export interface InstagramClient {
  publishPost(caption: string, imageUrl: string): Promise<PublishResult>;
  publishCarousel(caption: string, imageUrls: string[]): Promise<PublishResult>;
  getRecentMedia(limit?: number): Promise<InstagramMedia[]>;
  getComments(mediaId: string): Promise<InstagramComment[]>;
  replyComment(commentId: string, message: string): Promise<CommentReplyResult>;
  hideComment(commentId: string): Promise<boolean>;
  getMediaInsights(mediaId: string): Promise<MediaInsights>;
  getAccountInsights(period?: 'day' | 'week' | 'days_28'): Promise<AccountInsights>;
}
