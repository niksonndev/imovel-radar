import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import fs from 'node:fs';
import path from 'node:path';
import { MockTikTokClient } from '../src/infrastructure/tiktok/mock-client.js';

describe('MockTikTokClient', () => {
  const testStatePath = path.resolve(process.cwd(), '.test-tiktok-state.json');

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

  it('deve ter capabilities e plataforma TikTok configuradas', () => {
    const client = new MockTikTokClient(testStatePath);
    expect(client.platform).toBe('tiktok');
    expect(client.capabilities.video).toBe(true);
    expect(client.capabilities.carousel).toBe(true);
    expect(client.capabilities.hideComment).toBe(true);
    expect(client.capabilities.replyComment).toBe(true);
  });

  it('deve publicar post simples, carrossel photo mode e vídeo no mock', async () => {
    const client = new MockTikTokClient(testStatePath);

    // 1. Post simples
    const single = await client.publishPost(
      'Foto TikTok #imoveis',
      'https://example.com/slide1.png'
    );
    expect(single.mediaId).toBeDefined();

    // 2. Carrossel (Photo Mode 9:16)
    const carousel = await client.publishCarousel('Carrossel Photo Mode TikTok #fyp', [
      'https://example.com/slide1.png',
      'https://example.com/slide2.png',
      'https://example.com/slide3.png',
    ]);
    expect(carousel.mediaId).toBeDefined();

    // 3. Vídeo slideshow
    const video = await client.publishVideo(
      'Vídeo Slideshow TikTok #imoveis #maceio',
      'https://example.com/slideshow.mp4'
    );
    expect(video.mediaId).toBeDefined();

    const mediaList = await client.getRecentMedia(5);
    expect(mediaList.length).toBeGreaterThanOrEqual(3);
    expect(mediaList[0].caption).toContain('Vídeo Slideshow');
    expect(mediaList[0].mediaType).toBe('VIDEO');
  });

  it('deve gerenciar comentários no mock (adicionar, responder, ocultar)', async () => {
    const client = new MockTikTokClient(testStatePath);
    const mediaList = await client.getRecentMedia(1);
    const targetMedia = mediaList[0];

    const comment = client.addMockComment(
      targetMedia.id,
      'usuario_tiktok',
      'Qual o bairro mais valorizado?'
    );

    expect(comment.id).toBeDefined();
    expect(comment.text).toBe('Qual o bairro mais valorizado?');

    // Resposta
    const reply = await client.replyComment(
      comment.id,
      'Ponta Verde lidera o ranking! Veja no bot @imovelradar_bot'
    );
    expect(reply.replyId).toBeDefined();

    const comments = await client.getComments(targetMedia.id);
    const found = comments.find((c) => c.id === comment.id);
    expect(found?.replies?.length).toBe(1);
    expect(found?.replies?.[0]?.text).toContain('@imovelradar_bot');

    // Moderação (ocultar)
    const spamComment = client.addMockComment(
      targetMedia.id,
      'bot_spam',
      'Ganhe 10k por dia link na bio'
    );
    const hidden = await client.hideComment(spamComment.id);
    expect(hidden).toBe(true);

    const updatedComments = await client.getComments(targetMedia.id);
    const hiddenFound = updatedComments.find((c) => c.id === spamComment.id);
    expect(hiddenFound?.hidden).toBe(true);
  });

  it('deve retornar métricas de mídia e de conta TikTok mapeadas', async () => {
    const client = new MockTikTokClient(testStatePath);
    const mediaList = await client.getRecentMedia(1);

    const insights = await client.getMediaInsights(mediaList[0].id);
    expect(insights.reach).toBeGreaterThan(0);
    expect(insights.impressions).toBeGreaterThan(0);
    expect(insights.engagement).toBeGreaterThanOrEqual(0);

    const account = await client.getAccountInsights('week');
    expect(account.followerCount).toBeGreaterThan(0);
    expect(account.reach).toBeGreaterThan(0);
  });
});
