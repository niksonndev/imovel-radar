import { describe, it, expect } from 'vitest';
import { LLMService } from '../src/infrastructure/ai/llm-service.js';

describe('LLMService', () => {
  it('deve classificar comentários corretamente', async () => {
    const llm = new LLMService();

    const alertRes = await llm.classifyComment('Quero alerta para apto na ponta verde!');
    expect(alertRes.intent).toBe('ALERT_REQUEST');
    expect(alertRes.shouldHide).toBe(false);
    expect(alertRes.suggestedReply).toContain('Telegram');

    const spamRes = await llm.classifyComment('Ganhe seguidores e renda extra no link da bio');
    expect(spamRes.intent).toBe('SPAM');
    expect(spamRes.shouldHide).toBe(true);

    const priceRes = await llm.classifyComment('Qual o valor médio na Jatiúca?');
    expect(priceRes.intent).toBe('PRICE_QUERY');
    expect(priceRes.shouldHide).toBe(false);
  });
});
