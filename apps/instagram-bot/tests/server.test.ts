import { describe, it, expect, beforeAll, afterAll } from 'vitest';
import http from 'node:http';
import { createBotApp } from '../src/server.js';

describe('Server & Webhook HTTP', () => {
  let server: http.Server;
  let baseUrl: string;
  let db: any;

  beforeAll(async () => {
    const app = createBotApp();
    server = app.server;
    db = app.db;

    await new Promise<void>((resolve) => {
      server.listen(0, () => {
        const addr = server.address() as any;
        baseUrl = `http://localhost:${addr.port}`;
        resolve();
      });
    });
  });

  afterAll(async () => {
    await db.close();
    await new Promise<void>((resolve) => {
      server.close(() => resolve());
    });
  });

  it('GET /health deve retornar status 200 ok', async () => {
    const res = await fetch(`${baseUrl}/health`);
    expect(res.status).toBe(200);
    const body = (await res.json()) as any;
    expect(body.status).toBe('ok');
    expect(body.service).toBe('instagram-bot');
    expect(body.platforms).toContain('instagram');
    expect(body.platforms).toContain('tiktok');
  });

  it('GET e POST /webhook/tiktok devem responder corretamente', async () => {
    const getRes = await fetch(`${baseUrl}/webhook/tiktok`);
    expect(getRes.status).toBe(200);
    const getBody = (await getRes.json()) as any;
    expect(getBody.status).toBe('ok');

    const postRes = await fetch(`${baseUrl}/webhook/tiktok`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ event: 'publish.status', status: 'SUCCESS' }),
    });
    expect(postRes.status).toBe(200);
    const postBody = (await postRes.json()) as any;
    expect(postBody.received).toBe(true);
    expect(postBody.platform).toBe('tiktok');
  });

  it('GET /webhook deve verificar hub.challenge da Meta com token correto', async () => {
    const token = process.env.META_VERIFY_TOKEN || 'imovel_radar_verify_token_secret';
    const challenge = '1158201244';
    const res = await fetch(
      `${baseUrl}/webhook?hub.mode=subscribe&hub.verify_token=${token}&hub.challenge=${challenge}`
    );
    expect(res.status).toBe(200);
    const text = await res.text();
    expect(text).toBe(challenge);
  });

  it('GET /webhook deve rejeitar com 403 token incorreto', async () => {
    const res = await fetch(
      `${baseUrl}/webhook?hub.mode=subscribe&hub.verify_token=token_invalido&hub.challenge=123`
    );
    expect(res.status).toBe(403);
  });

  it('POST /webhook deve receber evento de comentário da Meta e responder 200', async () => {
    const payload = {
      object: 'instagram',
      entry: [
        {
          id: 'entry_1',
          time: 1710000000,
          changes: [
            {
              field: 'comments',
              value: {
                id: `webhook_comment_${Date.now()}`,
                text: 'Quero alerta na Ponta Verde!',
                from: { id: 'user_123', username: 'cliente_alerta' },
                media: { id: 'mock_media_101' },
              },
            },
          ],
        },
      ],
    };

    const res = await fetch(`${baseUrl}/webhook`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    expect(res.status).toBe(200);
    const data = (await res.json()) as { received: boolean };
    expect(data.received).toBe(true);
  });

  it('POST /api/content/generate não existe mais', async () => {
    const res = await fetch(`${baseUrl}/api/content/generate`, { method: 'POST' });
    expect(res.status).toBe(404);
  });
});
