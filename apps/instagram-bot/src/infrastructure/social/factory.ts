import { SocialClient, SocialPlatform } from './types.js';
import { createInstagramClient } from '../instagram/factory.js';
import { createTikTokClient } from '../tiktok/factory.js';

export function createSocialClient(
  platform: SocialPlatform = 'instagram'
): SocialClient {
  if (platform === 'tiktok') {
    return createTikTokClient();
  }
  return createInstagramClient();
}
