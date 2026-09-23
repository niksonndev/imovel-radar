import { describe, it, expect, beforeEach } from 'vitest';
import { CommentAgent } from '../src/agents/comment-agent/index.js';
import { DatabaseClient } from '../src/infrastructure/database/client.js';
import { LLMService } from '../src/infrastructure/ai/llm-service.js';
import { MockInstagramClient } from '../src/infrastructure/instagram/mock-client.js';

describe('CommentAgent', () => {
  let db: DatabaseClient;
  let llm: LLMService;
  let instagramClient: MockInstagramClient;
  let agent: CommentAgent;

  beforeEach(() => {
    db = new DatabaseClient();
    llm = new LLMService();
    instagramClient = new MockInstagramClient();
    agent = new CommentAgent({
      db,
      llm,
      instagramClient,
      autoHideSpam: true,
      autoReply: true,
    });
  });

  it('deve responder automaticamente pedidos de alerta com link do Telegram', async () => {
    const mediaList = await instagramClient.getRecentMedia(1);
    const mediaId = mediaList[0].id;

    const comment = instagramClient.addMockComment(
      mediaId,
      'alagoano_maceio',
      'Quero alerta de apartamento na Jatiúca!'
    );

    const result = await agent.processComment(comment, mediaId);

    expect(result.actionTaken).toBe('REPLIED');
    expect(result.analysis.intent).toBe('ALERT_REQUEST');
    expect(result.replyText).toContain('@imovelradar_bot');

    // Confirma que a resposta foi registrada no cliente do Instagram
    const comments = await instagramClient.getComments(mediaId);
    const updated = comments.find((c) => c.id === comment.id);
    expect(updated?.replies?.length).toBe(1);
    expect(updated?.replies?.[0]?.text).toContain('@imovelradar_bot');

    // Confirma auditoria no banco
    const logs = await agent.getLogs();
    expect(logs.some((l) => l.commentId === comment.id)).toBe(true);
  });

  it('deve ocultar automaticamente comentários identificados como SPAM', async () => {
    const mediaList = await instagramClient.getRecentMedia(1);
    const mediaId = mediaList[0].id;

    const spamComment = instagramClient.addMockComment(
      mediaId,
      'bot_golpe',
      'Ganhe seguidores e renda extra clicando no link da bio'
    );

    const result = await agent.processComment(spamComment, mediaId);

    expect(result.actionTaken).toBe('HIDDEN');
    expect(result.analysis.intent).toBe('SPAM');

    // Confirma que o comentário foi marcado como oculto
    const comments = await instagramClient.getComments(mediaId);
    const updated = comments.find((c) => c.id === spamComment.id);
    expect(updated?.hidden).toBe(true);
  });

  it('deve evitar responder comentários já processados (idempotência)', async () => {
    const mediaList = await instagramClient.getRecentMedia(1);
    const mediaId = mediaList[0].id;

    const comment = instagramClient.addMockComment(
      mediaId,
      'usuario_comum',
      'Excelente análise de preços!'
    );

    const first = await agent.processComment(comment, mediaId);
    expect(first.actionTaken).toBe('REPLIED');

    const second = await agent.processComment(comment, mediaId);
    expect(second.actionTaken).toBe('SKIPPED_ALREADY_HANDLED');
  });

  it('deve varrer e processar comentários em lote de posts recentes', async () => {
    const results = await agent.processRecentPostsComments(2);
    expect(results).toBeDefined();
    expect(Array.isArray(results)).toBe(true);
  });
});
