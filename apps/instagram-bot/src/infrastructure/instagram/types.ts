import {
  AccountInsights,
  CommentReplyResult,
  MediaInsights,
  PublishResult,
  SocialCapabilities,
  SocialClient,
  SocialComment,
  SocialMedia,
  SocialPlatform,
} from '../social/types.js';

export type {
  AccountInsights,
  CommentReplyResult,
  MediaInsights,
  PublishResult,
  SocialCapabilities,
  SocialClient,
  SocialPlatform,
};

export type InstagramMedia = SocialMedia;
export type InstagramComment = SocialComment;

export interface InstagramClient extends SocialClient {
  readonly platform: 'instagram';
}
