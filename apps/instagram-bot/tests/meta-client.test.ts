import { createHmac } from 'node:crypto';
import { describe, it, expect, vi, afterEach } from 'vitest';
import { MetaGraphInstagramClient } from '../src/infrastructure/instagram/meta-client.js';
import { verifyMetaSignature } from '../src/infrastructure/instagram/webhook-signature.js';
import { DEFAULT_GRAPH_API_VERSION } from '../src/infrastructure/instagram/constants.js';

describe('verifyMetaSignature', () => {
  it('aceita qualquer payload se o secret estiver vazio', () => {
    expect(verifyMetaSignature('{}', undefined, '')).toBe(true);
  });

  it('valida HMAC SHA-256 da Meta', () => {
    const secret = 'app-secret';
    const body = '{"object":"instagram"}';
    const digest = createHmac('sha256', secret).update(body, 'utf8').digest('hex');
    expect(verifyMetaSignature(body, `sha256=${digest}`, secret)).toBe(true);
    expect(verifyMetaSignature(body, 'sha256=deadbeef', secret)).toBe(false);
  });
});

describe('MetaGraphInstagramClient', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('usa Graph API v26 e form-urlencoded no POST', async () => {
    const calls: Array<{ url: string; init?: RequestInit }> = [];
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string | URL, init?: RequestInit) => {
        calls.push({ url: String(url), init });
        const href = String(url);
        if (href.includes('/media_publish')) {
          return new Response(JSON.stringify({ id: 'published_1' }), { status: 200 });
        }
        if (href.includes('/IG123/media') && init?.method === 'POST') {
          return new Response(JSON.stringify({ id: 'container_1' }), { status: 200 });
        }
        if (href.includes('/container_1')) {
          return new Response(JSON.stringify({ status_code: 'FINISHED' }), { status: 200 });
        }
        return new Response(JSON.stringify({ error: { message: 'unexpected' } }), {
          status: 400,
        });
      })
    );

    const client = new MetaGraphInstagramClient({
      accountId: 'IG123',
      accessToken: 'token',
      statusPollMs: 1,
      containerTimeoutMs: 1000,
    });

    const result = await client.publishPost('caption', 'https://cdn.example/img.png');
    expect(result.mediaId).toBe('published_1');
    expect(calls[0].url).toContain(`/${DEFAULT_GRAPH_API_VERSION}/`);
    expect(calls[0].init?.method).toBe('POST');
    const headers = calls[0].init?.headers as Record<string, string>;
    expect(headers['Content-Type']).toBe('application/x-www-form-urlencoded');
    expect(String(calls[0].init?.body)).toContain('image_url=');
    expect(String(calls[0].init?.body)).not.toMatch(/^\{/);
  });

  it('espera FINISHED antes de publicar o contêiner', async () => {
    let statusCalls = 0;
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string | URL, init?: RequestInit) => {
        const href = String(url);
        if (href.includes('/IG123/media') && init?.method === 'POST' && !href.includes('media_publish')) {
          return new Response(JSON.stringify({ id: 'c1' }), { status: 200 });
        }
        if (href.includes('/c1') && (!init?.method || init.method === 'GET')) {
          statusCalls += 1;
          const code = statusCalls < 2 ? 'IN_PROGRESS' : 'FINISHED';
          return new Response(JSON.stringify({ status_code: code }), { status: 200 });
        }
        if (href.includes('media_publish')) {
          return new Response(JSON.stringify({ id: 'p1' }), { status: 200 });
        }
        return new Response(JSON.stringify({ error: { message: href } }), { status: 400 });
      })
    );

    const client = new MetaGraphInstagramClient({
      accountId: 'IG123',
      accessToken: 'token',
      statusPollMs: 1,
      containerTimeoutMs: 5000,
    });

    await client.publishPost('x', 'https://cdn.example/a.png');
    expect(statusCalls).toBeGreaterThanOrEqual(2);
  });
});
