import http from 'node:http';
import dotenv from 'dotenv';
import { DatabaseClient } from './infrastructure/database/client.js';
import { LLMService } from './infrastructure/ai/llm-service.js';
import { createInstagramClient } from './infrastructure/instagram/index.js';
import { createTikTokClient } from './infrastructure/tiktok/index.js';
import { verifyMetaSignature } from './infrastructure/instagram/webhook-signature.js';
import { CommentAgent } from './agents/comment-agent/index.js';

dotenv.config();

const port = Number(process.env.PORT) || 3000;
const verifyToken = process.env.META_VERIFY_TOKEN || 'imovel_radar_verify_token_secret';
const metaAppSecret = process.env.META_APP_SECRET || '';

export function createBotApp() {
  const db = new DatabaseClient();
  const llm = new LLMService();
  const instagramClient = createInstagramClient();
  const tiktokClient = createTikTokClient();

  const commentAgent = new CommentAgent({
    db,
    llm,
    socialClient: instagramClient,
    autoHideSpam: true,
    autoReply: true,
  });

  const server = http.createServer(async (req, res) => {
    const parsedUrl = new URL(req.url || '/', `http://${req.headers.host || 'localhost'}`);
    const pathname = parsedUrl.pathname;
    const method = req.method;

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

    if (pathname === '/webhook' && method === 'POST') {
      let body = '';
      req.on('data', (chunk) => {
        body += chunk;
      });

      req.on('end', async () => {
        try {
          const shouldVerify = Boolean(metaAppSecret) && !process.env.VITEST;
          const signature = req.headers['x-hub-signature-256'];
          const sigHeader = Array.isArray(signature) ? signature[0] : signature;
          if (shouldVerify && !verifyMetaSignature(body, sigHeader, metaAppSecret)) {
            res.writeHead(403, { 'Content-Type': 'application/json' });
            res.end(JSON.stringify({ error: 'Invalid signature' }));
            return;
          }

          const payload = JSON.parse(body || '{}');

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
                  console.log(
                    `[Webhook] Novo comentário recebido de @${commentData.username}: "${commentData.text}"`
                  );
                  await commentAgent.processComment(commentData, commentData.mediaId);
                }
              }
            }
          }

          res.writeHead(200, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ received: true }));
        } catch (err: unknown) {
          const message = err instanceof Error ? err.message : 'Erro desconhecido';
          console.error('[Webhook] Erro ao processar payload:', err);
          res.writeHead(400, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ error: message }));
        }
      });
      return;
    }

    if (pathname === '/webhook/tiktok' && method === 'GET') {
      const challenge =
        parsedUrl.searchParams.get('challenge') || parsedUrl.searchParams.get('hub.challenge');
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
        } catch (err: unknown) {
          const message = err instanceof Error ? err.message : 'Erro desconhecido';
          console.error('[TikTokWebhook] Erro no payload:', err);
          res.writeHead(400, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ error: message }));
        }
      });
      return;
    }

    res.writeHead(404, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ error: 'Not Found' }));
  });

  return {
    server,
    db,
    commentAgent,
    instagramClient,
    tiktokClient,
  };
}

if (process.argv[1] && process.argv[1].endsWith('server.ts')) {
  const { server } = createBotApp();
  server.listen(port, '0.0.0.0', () => {
    console.log(`🚀 [SocialBot] Webhook de comentários em 0.0.0.0:${port}`);
    console.log(`   - Instagram Webhook: http://localhost:${port}/webhook`);
    console.log(`   - TikTok Webhook:    http://localhost:${port}/webhook/tiktok`);
    console.log(`   - Health URL:        http://localhost:${port}/health`);
  });
}
