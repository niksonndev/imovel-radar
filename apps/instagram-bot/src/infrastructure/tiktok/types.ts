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
  SocialComment,
  SocialMedia,
  SocialPlatform,
};

export type TikTokMedia = SocialMedia;
export type TikTokComment = SocialComment;

export interface TikTokClient extends SocialClient {
  readonly platform: 'tiktok';
}

export type TikTokPrivacyLevel =
  | 'PUBLIC_TO_EVERYONE'
  | 'MUTUAL_FOLLOW_FRIENDS'
  | 'FOLLOWER_OF_CREATOR'
  | 'SELF_ONLY';

export interface TikTokOpenApiClientConfig {
  clientKey?: string;
  clientSecret?: string;
  accessToken: string;
  baseUrl?: string;
  privacyLevel?: TikTokPrivacyLevel;
  autoAddMusic?: boolean;
  brandOrganicToggle?: boolean;
}
