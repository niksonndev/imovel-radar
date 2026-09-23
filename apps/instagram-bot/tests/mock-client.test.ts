import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import fs from 'node:fs';
import path from 'node:path';
import { MockInstagramClient } from '../src/infrastructure/instagram/mock-client.js';

describe('MockInstagramClient', () => {
  const testStatePath = path.resolve(process.cwd(), '.test-instagram-state.json');

  beforeEach(() => {
    if (fs.existsSync(testStatePath)) {
      fs.unlinkSync(testStatePath);
    }
  });

  afterEach(() => {
    if (fs.existsSync(testStatePath)) {
      fs.unlinkSync(testStatePath);
    }
  });

  it('deve publicar post e carrossel simulados', async () => {
    const client = new MockInstagramClient(testStatePath);

    const post = await client.publishPost(
      'Teste de post simples',
      'https://example.com/card.png'
    );
    expect(post.mediaId).toBeDefined();

    const carousel = await client.publishCarousel('Teste carrossel', [
      'https://example.com/card1.png',
      'https://example.com/card2.png',
    ]);
    expect(carousel.mediaId).toBeDefined();

    const mediaList = await client.getRecentMedia(5);
    expect(mediaList.length).toBeGreaterThanOrEqual(2);
    expect(mediaList[0].caption).toBe('Teste carrossel');
  });

  it('deve responder comentário e atualizar contadores', async () => {
    const client = new MockInstagramClient(testStatePath);
    const mediaList = await client.getRecentMedia(1);
    const targetMedia = mediaList[0];

    const comment = client.addMockComment(
      targetMedia.id,
      'usuario_teste',
      'ALERTA 2 quartos Jatiúca'
    );

    const reply = await client.replyComment(
      comment.id,
      'Olá! Veja no Telegram: @imovelradar_bot'
    );

    expect(reply.replyId).toBeDefined();
    expect(reply.parentCommentId).toBe(comment.id);

    const comments = await client.getComments(targetMedia.id);
    const found = comments.find((c) => c.id === comment.id);
    expect(found?.replies?.length).toBe(1);
    expect(found?.replies?.[0]?.text).toContain('@imovelradar_bot');
  });

  it('deve ocultar comentário de spam', async () => {
    const client = new MockInstagramClient(testStatePath);
    const mediaList = await client.getRecentMedia(1);
    const comment = client.addMockComment(
      mediaList[0].id,
      'spammer',
      'Ganhe dinheiro fácil'
    );

    const hidden = await client.hideComment(comment.id);
    expect(hidden).toBe(true);

    const comments = await client.getComments(mediaList[0].id);
    const found = comments.find((c) => c.id === comment.id);
    expect(found?.hidden).toBe(true);
  });

  it('deve retornar insights de mídia e de conta', async () => {
    const client = new MockInstagramClient(testStatePath);
    const mediaList = await client.getRecentMedia(1);

    const insights = await client.getMediaInsights(mediaList[0].id);
    expect(insights.reach).toBeGreaterThan(0);
    expect(insights.impressions).toBeGreaterThanOrEqual(insights.reach);

    const account = await client.getAccountInsights('week');
    expect(account.followerCount).toBeGreaterThan(0);
    expect(account.reach).toBeGreaterThan(0);
  });
});
