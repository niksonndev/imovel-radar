import http from 'node:http';
import dotenv from 'dotenv';
import { DatabaseClient } from './infrastructure/database/client.js';
import { LLMService } from './infrastructure/ai/llm-service.js';
import { CardGenerator } from './infrastructure/renderer/card-generator.js';
import { VideoSlideshowGenerator } from './infrastructure/renderer/video-slideshow.js';
import { createInstagramClient } from './infrastructure/instagram/index.js';
import { createTikTokClient } from './infrastructure/tiktok/index.js';
import { SocialPlatform } from './infrastructure/social/types.js';
import { ContentManagerAgent } from './agents/content-manager/index.js';
import { CommentAgent } from './agents/comment-agent/index.js';
import { AnalyticsAgent } from './agents/analytics-agent/index.js';

dotenv.config();

const port = Number(process.env.PORT) || 3000;
const verifyToken = process.env.META_VERIFY_TOKEN || 'imovel_radar_verify_token_secret';

export function createBotApp() {
  const db = new DatabaseClient();
  const llm = new LLMService();
  const cardGenerator = new CardGenerator();
  const videoGenerator = new VideoSlideshowGenerator();
  const instagramClient = createInstagramClient();
  const tiktokClient = createTikTokClient();

  const contentManager = new ContentManagerAgent({
    db,
    llm,
    cardGenerator,
    videoGenerator,
    socialClient: instagramClient,
  });

  const commentAgent = new CommentAgent({
    db,
    llm,
    socialClient: instagramClient,
    autoHideSpam: true,
    autoReply: true,
  });

  const analyticsAgent = new AnalyticsAgent({
    db,
    llm,
    socialClient: instagramClient,
    contentManager,
  });

  const tiktokContentManager = new ContentManagerAgent({
    db,
    llm,
    cardGenerator,
    videoGenerator,
    socialClient: tiktokClient,
  });

  const tiktokCommentAgent = new CommentAgent({
    db,
    llm,
    socialClient: tiktokClient,
    autoHideSpam: true,
    autoReply: true,
  });

  const tiktokAnalyticsAgent = new AnalyticsAgent({
    db,
    llm,
    socialClient: tiktokClient,
    contentManager: tiktokContentManager,
  });

  const server = http.createServer(async (req, res) => {
    const parsedUrl = new URL(req.url || '/', `http://${req.headers.host || 'localhost'}`);
    const pathname = parsedUrl.pathname;
    const method = req.method;

    // 1. Healthcheck
    if (pathname === '/health' && method === 'GET') {
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(
        JSON.stringify({
          status: 'ok',
          service: 'instagram-bot',
          platforms: ['instagram', 'tiktok'],
          timestamp: new Date(),
        })
      );
      return;
    }

    // 2. Meta Webhook Verification (GET)
    if (pathname === '/webhook' && method === 'GET') {
      const mode = parsedUrl.searchParams.get('hub.mode');
      const token = parsedUrl.searchParams.get('hub.verify_token');
      const challenge = parsedUrl.searchParams.get('hub.challenge');

      if (mode === 'subscribe' && token === verifyToken) {
        console.log('[Webhook] Verificação da Meta realizada com sucesso.');
        res.writeHead(200, { 'Content-Type': 'text/plain' });
        res.end(challenge);
      } else {
        console.warn('[Webhook] Falha de verificação de token:', { mode, token });
        res.writeHead(403, { 'Content-Type': 'text/plain' });
        res.end('Forbidden');
      }
      return;
    }

    // 3. Meta Webhook Event Receiver (POST)
    if (pathname === '/webhook' && method === 'POST') {
      let body = '';
      req.on('data', (chunk) => {
        body += chunk;
      });

      req.on('end', async () => {
        try {
          const payload = JSON.parse(body || '{}');

          // Processa entradas do webhook da Meta
          if (payload.object === 'instagram' && Array.isArray(payload.entry)) {
            for (const entry of payload.entry) {
              const changes = entry.changes || [];
              for (const change of changes) {
                if (change.field === 'comments') {
                  const val = change.value;
                  const commentData = {
                    id: val.id,
                    mediaId: val.media?.id || 'unknown_media',
                    text: val.text || '',
                    username: val.from?.username || 'user',
                    timestamp: new Date().toISOString(),
                  };
                  console.log(`[Webhook] Novo comentário recebido de @${commentData.username}: "${commentData.text}"`);
                  await commentAgent.processComment(commentData, commentData.mediaId);
                }
              }
            }
          }

          res.writeHead(200, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ received: true }));
        } catch (err: any) {
          console.error('[Webhook] Erro ao processar payload:', err);
          res.writeHead(400, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ error: err.message }));
        }
      });
      return;
    }

    // 4. TikTok Webhook Verification & Event Ingress (GET/POST)
    if (pathname === '/webhook/tiktok' && method === 'GET') {
      const challenge = parsedUrl.searchParams.get('challenge') || parsedUrl.searchParams.get('hub.challenge');
      if (challenge) {
        res.writeHead(200, { 'Content-Type': 'text/plain' });
        res.end(challenge);
        return;
      }
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ status: 'ok', service: 'tiktok-webhook' }));
      return;
    }

    if (pathname === '/webhook/tiktok' && method === 'POST') {
      let body = '';
      req.on('data', (chunk) => {
        body += chunk;
      });

      req.on('end', async () => {
        try {
          const payload = JSON.parse(body || '{}');
          console.log('[TikTokWebhook] Evento recebido:', payload.event || payload);
          res.writeHead(200, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ received: true, platform: 'tiktok' }));
        } catch (err: any) {
          console.error('[TikTokWebhook] Erro no payload:', err);
          res.writeHead(400, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ error: err.message }));
        }
      });
      return;
    }

    // 5. Disparo manual de agentes via HTTP
    if (pathname === '/api/content/generate' && method === 'POST') {
      let body = '';
      req.on('data', (chunk) => {
        body += chunk;
      });

      req.on('end', async () => {
        try {
          const parsed = body ? JSON.parse(body) : {};
          const targetPlatform: SocialPlatform = parsed.platform === 'tiktok' ? 'tiktok' : 'instagram';
          const targetFormat = parsed.format === 'video' ? 'video' : 'photo';

          const targetAgent = targetPlatform === 'tiktok' ? tiktokContentManager : contentManager;
          const post = await targetAgent.generatePost({
            platform: targetPlatform,
            format: targetFormat,
          });

          res.writeHead(200, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ success: true, platform: targetPlatform, post }));
        } catch (err: any) {
          res.writeHead(500, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ error: err.message }));
        }
      });
      return;
    }

    if (pathname === '/api/analytics/report' && method === 'GET') {
      try {
        const platformParam = parsedUrl.searchParams.get('platform');
        const isTikTok = platformParam?.toLowerCase() === 'tiktok';
        const targetAgent = isTikTok ? tiktokAnalyticsAgent : analyticsAgent;

        const report = await targetAgent.generateReport('week');
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify(report));
      } catch (err: any) {
        res.writeHead(500, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ error: err.message }));
      }
      return;
    }

    res.writeHead(404, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ error: 'Not Found' }));
  });

  return {
    server,
    db,
    contentManager,
    commentAgent,
    analyticsAgent,
    instagramClient,
    tiktokClient,
    tiktokContentManager,
    tiktokCommentAgent,
    tiktokAnalyticsAgent,
  };
}

// Inicia servidor se executado diretamente
if (process.argv[1] && process.argv[1].endsWith('server.ts')) {
  const { server } = createBotApp();
  server.listen(port, '0.0.0.0', () => {
    console.log(`🚀 [SocialBot] Servidor rodando em 0.0.0.0:${port}`);
    console.log(`   - Instagram Webhook: http://localhost:${port}/webhook`);
    console.log(`   - TikTok Webhook:    http://localhost:${port}/webhook/tiktok`);
    console.log(`   - Health URL:        http://localhost:${port}/health`);
  });
}
