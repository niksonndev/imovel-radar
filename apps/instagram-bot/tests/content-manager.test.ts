import { describe, it, expect } from 'vitest';
import { ContentManagerAgent } from '../src/agents/content-manager/index.js';
import { DatabaseClient } from '../src/infrastructure/database/client.js';
import { LLMService } from '../src/infrastructure/ai/llm-service.js';
import { CardGenerator } from '../src/infrastructure/renderer/card-generator.js';
import { MockInstagramClient } from '../src/infrastructure/instagram/mock-client.js';

describe('ContentManagerAgent', () => {
  it('deve gerar post completo com pauta, copy, slides SVG e status DRAFT', async () => {
    const db = new DatabaseClient();
    const llm = new LLMService();
    const cardGenerator = new CardGenerator();
    const instagramClient = new MockInstagramClient();

    const agent = new ContentManagerAgent({
      db,
      llm,
      cardGenerator,
      instagramClient,
    });

    const post = await agent.generatePost({ type: 'PRICE_RANKING' });

    expect(post.id).toBeDefined();
    expect(post.status).toBe('DRAFT');
    expect(post.postType).toBe('CAROUSEL');
    expect(post.slides.length).toBe(4);
    expect(post.caption).toContain('ALERTA');
    expect(post.slides[0].svgContent).toContain('<svg');
  });

  it('deve publicar post e atualizar status para PUBLISHED com mediaId', async () => {
    const db = new DatabaseClient();
    const llm = new LLMService();
    const cardGenerator = new CardGenerator();
    const instagramClient = new MockInstagramClient();

    const agent = new ContentManagerAgent({
      db,
      llm,
      cardGenerator,
      instagramClient,
    });

    const post = await agent.generatePost({ type: 'OPPORTUNITY_DEAL' });
    const publishRes = await agent.publishPost(post.id);

    expect(publishRes.mediaId).toBeDefined();

    const updated = await db.getPost(post.id);
    expect(updated?.status).toBe('PUBLISHED');
    expect(updated?.mediaId).toBe(publishRes.mediaId);
    expect(updated?.publishedAt).toBeDefined();
  });

  it('deve agendar e processar fila de posts agendados', async () => {
    const db = new DatabaseClient();
    const llm = new LLMService();
    const cardGenerator = new CardGenerator();
    const instagramClient = new MockInstagramClient();

    const agent = new ContentManagerAgent({
      db,
      llm,
      cardGenerator,
      instagramClient,
    });

    const post = await agent.generatePost();
    await agent.schedulePost(post.id, new Date(Date.now() - 1000)); // Já no passado para disparar

    const queueRes = await agent.processQueue();
    expect(queueRes.length).toBeGreaterThanOrEqual(1);
    expect(queueRes.find((r) => r.postId === post.id)?.result?.mediaId).toBeDefined();

    const published = await db.getPost(post.id);
    expect(published?.status).toBe('PUBLISHED');
  });
});
