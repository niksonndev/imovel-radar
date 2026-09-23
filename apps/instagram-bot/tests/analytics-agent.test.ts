import { describe, it, expect } from 'vitest';
import { AnalyticsAgent } from '../src/agents/analytics-agent/index.js';
import { ContentManagerAgent } from '../src/agents/content-manager/index.js';
import { DatabaseClient } from '../src/infrastructure/database/client.js';
import { LLMService } from '../src/infrastructure/ai/llm-service.js';
import { CardGenerator } from '../src/infrastructure/renderer/card-generator.js';
import { MockInstagramClient } from '../src/infrastructure/instagram/mock-client.js';

describe('AnalyticsAgent', () => {
  it('deve gerar relatório executivo com totais, insights de IA e sugestões de pauta', async () => {
    const db = new DatabaseClient();
    const llm = new LLMService();
    const instagramClient = new MockInstagramClient();

    const agent = new AnalyticsAgent({
      db,
      llm,
      instagramClient,
    });

    const report = await agent.generateReport('week');

    expect(report.period).toBe('week');
    expect(report.totals.totalReach).toBeGreaterThan(0);
    expect(report.totals.totalImpressions).toBeGreaterThan(0);
    expect(report.mediaPerformance.length).toBeGreaterThan(0);
    expect(report.executiveSummary).toBeDefined();
    expect(report.keyInsights.length).toBeGreaterThan(0);
    expect(report.strategicPautas.length).toBeGreaterThan(0);

    const md = agent.formatReportMarkdown(report);
    expect(md).toContain('Relatório Executivo de Performance Instagram');
    expect(md).toContain('Alcance Total:');
  });

  it('deve retroalimentar o ContentManagerAgent com pautas automáticas (Feedback Loop)', async () => {
    const db = new DatabaseClient();
    const llm = new LLMService();
    const cardGenerator = new CardGenerator();
    const instagramClient = new MockInstagramClient();

    const contentManager = new ContentManagerAgent({
      db,
      llm,
      cardGenerator,
      instagramClient,
    });

    const analyticsAgent = new AnalyticsAgent({
      db,
      llm,
      instagramClient,
      contentManager,
    });

    const created = await analyticsAgent.feedbackToContentManager();

    expect(created.length).toBeGreaterThan(0);
    expect(created[0].postId).toBeDefined();

    const posts = await contentManager.listPosts('DRAFT');
    expect(posts.length).toBeGreaterThanOrEqual(1);
  });
});
