import { TikTokClient } from './types.js';
import { MockTikTokClient } from './mock-client.js';
import { TikTokOpenApiClient } from './open-api-client.js';

export function createTikTokClient(): TikTokClient {
  const mode = (process.env.TIKTOK_MODE || 'MOCK').toUpperCase();

  if (mode === 'LIVE') {
    const accessToken = process.env.TIKTOK_ACCESS_TOKEN;

    if (!accessToken) {
      console.warn(
        '[TikTokClient] MODO LIVE solicitado, mas TIKTOK_ACCESS_TOKEN ausente. Usando MockTikTokClient como fallback seguro.'
      );
      return new MockTikTokClient();
    }

    return new TikTokOpenApiClient({
      clientKey: process.env.TIKTOK_CLIENT_KEY,
      clientSecret: process.env.TIKTOK_CLIENT_SECRET,
      accessToken,
      baseUrl: process.env.TIKTOK_BASE_URL,
      privacyLevel: (process.env.TIKTOK_PRIVACY_LEVEL as any) || 'SELF_ONLY',
    });
  }

  return new MockTikTokClient();
}
