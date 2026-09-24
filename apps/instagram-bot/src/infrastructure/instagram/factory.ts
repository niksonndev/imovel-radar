import {
  DEFAULT_GRAPH_API_HOST,
  DEFAULT_GRAPH_API_VERSION,
} from './constants.js';
import { InstagramClient } from './types.js';
import { MockInstagramClient } from './mock-client.js';
import { MetaGraphInstagramClient } from './meta-client.js';

export function createInstagramClient(): InstagramClient {
  const mode = (process.env.INSTAGRAM_MODE || 'MOCK').toUpperCase();

  if (mode === 'LIVE') {
    const accountId = process.env.INSTAGRAM_ACCOUNT_ID;
    const accessToken = process.env.INSTAGRAM_ACCESS_TOKEN;

    if (!accountId || !accessToken) {
      console.warn(
        '[InstagramClient] MODO LIVE solicitado, mas INSTAGRAM_ACCOUNT_ID ou INSTAGRAM_ACCESS_TOKEN ausente. Usando MockInstagramClient como fallback seguro.'
      );
      return new MockInstagramClient();
    }

    return new MetaGraphInstagramClient({
      accountId,
      accessToken,
      apiVersion: process.env.GRAPH_API_VERSION || DEFAULT_GRAPH_API_VERSION,
      apiHost: process.env.GRAPH_API_HOST || DEFAULT_GRAPH_API_HOST,
    });
  }

  return new MockInstagramClient();
}
