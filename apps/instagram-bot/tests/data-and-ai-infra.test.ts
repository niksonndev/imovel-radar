import { describe, it, expect } from 'vitest';
import { DatabaseClient } from '../src/infrastructure/database/client.js';
import { LLMService } from '../src/infrastructure/ai/llm-service.js';
import { CardGenerator } from '../src/infrastructure/renderer/card-generator.js';

describe('Data & AI Infrastructure', () => {
  it('DatabaseClient deve retornar snapshot e deals de Maceió (com fallback seguro)', async () => {
    const db = new DatabaseClient();
    const snapshot = await db.getLatestMarketSnapshot('maceio');

    expect(snapshot).toBeDefined();
    expect(snapshot?.payload.maceio?.rental?.summary.sample).toBeGreaterThan(0);
    expect(snapshot?.payload.maceio?.rental?.neighbourhoods.length).toBeGreaterThan(0);

    const deals = await db.getTopDeals({ municipality: 'Maceió', limit: 3 });
    expect(deals.length).toBeGreaterThanOrEqual(1);
    expect(deals[0].neighbourhood).toBeDefined();

    await db.close();
  });

  it('LLMService deve gerar copy de carrossel contextual com CTA e hashtags', async () => {
    const db = new DatabaseClient();
    const llm = new LLMService();

    const snapshot = await db.getLatestMarketSnapshot('maceio');
    const rentalData = snapshot!.payload.maceio!.rental!;
    const deals = await db.getTopDeals();

    const copy = await llm.generateContentCopy(
      { type: 'PRICE_RANKING' },
      rentalData,
      deals
    );

    expect(copy.title).toBeDefined();
    expect(copy.hook).toContain('Maceió');
    expect(copy.slides.length).toBe(4);
    expect(copy.cta).toContain('ALERTA');
    expect(copy.hashtags).toContain('#maceio');

    await db.close();
  });

  it('LLMService deve classificar comentários corretamente', async () => {
    const llm = new LLMService();

    // 1. Pedido de alerta
    const alertRes = await llm.classifyComment('Quero alerta para apto na ponta verde!');
    expect(alertRes.intent).toBe('ALERT_REQUEST');
    expect(alertRes.shouldHide).toBe(false);
    expect(alertRes.suggestedReply).toContain('Telegram');

    // 2. Spam
    const spamRes = await llm.classifyComment('Ganhe seguidores e renda extra no link da bio');
    expect(spamRes.intent).toBe('SPAM');
    expect(spamRes.shouldHide).toBe(true);

    // 3. Dúvida de preço
    const priceRes = await llm.classifyComment('Qual o valor médio na Jatiúca?');
    expect(priceRes.intent).toBe('PRICE_QUERY');
    expect(priceRes.shouldHide).toBe(false);
  });

  it('CardGenerator deve criar slides SVG válidos', async () => {
    const generator = new CardGenerator();
    const slides = [
      { title: 'Ranking do m² em Maceió', body: 'Confira os bairros mais valorizados', highlightedMetric: 'Topo: Ponta Verde' },
      { title: 'Top Bairros', body: '1. Ponta Verde: R$ 44/m²\n2. Jatiúca: R$ 41/m²' },
      { title: 'Ative seu Alerta', body: 'Receba no Telegram' },
    ];

    const results = await generator.generateCarouselSlides('test_post_1', slides);
    expect(results.length).toBe(3);
    expect(results[0].svgContent).toContain('<svg');
    expect(results[0].svgContent).toContain('Ranking do m² em Maceió');
    expect(results[2].svgContent).toContain('COMENTE "ALERTA"');
  });
});
