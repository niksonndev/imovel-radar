import { describe, it, expect, vi } from 'vitest';
import { ContentManagerAgent } from '../src/agents/content-manager/index.js';
import { DatabaseClient } from '../src/infrastructure/database/client.js';
import { LLMService } from '../src/infrastructure/ai/llm-service.js';
import { CardGenerator } from '../src/infrastructure/renderer/card-generator.js';
import { MockInstagramClient } from '../src/infrastructure/instagram/mock-client.js';
import { MockTikTokClient } from '../src/infrastructure/tiktok/mock-client.js';

describe('ContentManagerAgent', () => {
  it('deve gerar post completo com pauta, copy, slides SVG e status DRAFT', async () => {
    const db = new DatabaseClient();
    const llm = new LLMService();
    const cardGenerator = new CardGenerator();
    const instagramClient = new MockInstagramClient();
    const carouselSpy = vi.spyOn(instagramClient, 'publishCarousel');
    const singleSpy = vi.spyOn(instagramClient, 'publishPost');
    const videoSpy = vi.spyOn(instagramClient, 'publishVideo');

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
    expect(post.slides[0].localPath).toMatch(/\.png$/);
    expect(carouselSpy).not.toHaveBeenCalled();
    expect(singleSpy).not.toHaveBeenCalled();
    expect(videoSpy).not.toHaveBeenCalled();
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

    await expect(agent.publishPost(post.id)).rejects.toThrow(/já foi publicado/);
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

  it('deve gerar e publicar post no TikTok Photo Mode (9:16)', async () => {
    const db = new DatabaseClient();
    const llm = new LLMService();
    const cardGenerator = new CardGenerator();
    const tiktokClient = new MockTikTokClient();

    const agent = new ContentManagerAgent({
      db,
      llm,
      cardGenerator,
      socialClient: tiktokClient,
    });

    const post = await agent.generatePost({
      platform: 'tiktok',
      format: 'photo',
      type: 'PRICE_RANKING',
    });

    expect(post.platform).toBe('tiktok');
    expect(post.postType).toBe('CAROUSEL');
    expect(post.caption).toContain('#fyp');
    expect(post.slides[0].svgContent).toContain('height="1920"');

    const publishRes = await agent.publishPost(post.id);
    expect(publishRes.mediaId).toBeDefined();

    const stored = await db.getPost(post.id);
    expect(stored?.status).toBe('PUBLISHED');
    expect(stored?.platform).toBe('tiktok');
  });

  it('deve gerar e publicar post no TikTok em formato VIDEO slideshow', async () => {
    const db = new DatabaseClient();
    const llm = new LLMService();
    const cardGenerator = new CardGenerator();
    const tiktokClient = new MockTikTokClient();

    const agent = new ContentManagerAgent({
      db,
      llm,
      cardGenerator,
      socialClient: tiktokClient,
    });

    const post = await agent.generatePost({
      platform: 'tiktok',
      format: 'video',
      type: 'OPPORTUNITY_DEAL',
    });

    expect(post.platform).toBe('tiktok');
    expect(post.postType).toBe('VIDEO');
    expect(post.videoUrl).toBeDefined();
    expect(post.videoUrl?.endsWith('.mp4')).toBe(true);

    const publishRes = await agent.publishPost(post.id);
    expect(publishRes.mediaId).toBeDefined();

    const stored = await db.getPost(post.id);
    expect(stored?.status).toBe('PUBLISHED');
    expect(stored?.postType).toBe('VIDEO');
  });
});
