import { describe, it, expect } from 'vitest';
import { AnalyticsAgent } from '../src/agents/analytics-agent/index.js';
import { DatabaseClient } from '../src/infrastructure/database/client.js';
import { LLMService } from '../src/infrastructure/ai/llm-service.js';
import { MockInstagramClient } from '../src/infrastructure/instagram/mock-client.js';
import { MockTikTokClient } from '../src/infrastructure/tiktok/mock-client.js';

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

  it('deve gerar relatório executivo para TikTok e salvar snapshot com platform: tiktok', async () => {
    const db = new DatabaseClient();
    const llm = new LLMService();
    const tiktokClient = new MockTikTokClient();

    const agent = new AnalyticsAgent({
      db,
      llm,
      socialClient: tiktokClient,
    });

    const report = await agent.generateReport('week');
    expect(report.period).toBe('week');
    expect(report.totals.totalReach).toBeGreaterThan(0);

    const md = agent.formatReportMarkdown(report);
    expect(md).toContain('Relatório Executivo de Performance TikTok');

    const snapshots = await db.getRecentAnalytics(5, 'tiktok');
    expect(snapshots.length).toBeGreaterThanOrEqual(1);
    expect(snapshots[0].platform).toBe('tiktok');
  });
});
