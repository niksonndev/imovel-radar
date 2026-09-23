import {
  DatabaseClient,
  AnalyticsSnapshotRecord,
} from '../../infrastructure/database/client.js';
import { LLMService, PerformanceAnalysis } from '../../infrastructure/ai/llm-service.js';
import {
  AccountInsights,
  InstagramClient,
  InstagramMedia,
  MediaInsights,
} from '../../infrastructure/instagram/types.js';
import { ContentManagerAgent } from '../content-manager/index.js';

export interface AnalyticsAgentOptions {
  db: DatabaseClient;
  llm: LLMService;
  instagramClient: InstagramClient;
  contentManager?: ContentManagerAgent;
}

export interface MediaPerformanceItem {
  media: InstagramMedia;
  insights: MediaInsights;
  engagementRate: number;
}

export interface AnalyticsReport {
  generatedAt: Date;
  period: 'day' | 'week' | 'days_28';
  account: AccountInsights;
  mediaPerformance: MediaPerformanceItem[];
  totals: {
    totalReach: number;
    totalImpressions: number;
    totalSaved: number;
    totalShares: number;
    averageEngagementRate: number;
  };
  executiveSummary: string;
  keyInsights: string[];
  strategicPautas: PerformanceAnalysis['nextPautas'];
}

export class AnalyticsAgent {
  private db: DatabaseClient;
  private llm: LLMService;
  private instagramClient: InstagramClient;
  private contentManager?: ContentManagerAgent;

  constructor(options: AnalyticsAgentOptions) {
    this.db = options.db;
    this.llm = options.llm;
    this.instagramClient = options.instagramClient;
    this.contentManager = options.contentManager;
  }

  /**
   * Coleta métricas de conta e mídias recentes, calcula taxas de engajamento
   * e gera o relatório completo de performance com IA.
   */
  async generateReport(period: 'day' | 'week' | 'days_28' = 'week'): Promise<AnalyticsReport> {
    const account = await this.instagramClient.getAccountInsights(period);
    const recentMedia = await this.instagramClient.getRecentMedia(10);

    const mediaPerformance: MediaPerformanceItem[] = [];
    let totalReach = 0;
    let totalImpressions = 0;
    let totalSaved = 0;
    let totalShares = 0;
    let totalInteractions = 0;

    for (const media of recentMedia) {
      const insights = await this.instagramClient.getMediaInsights(media.id);
      const reach = Math.max(insights.reach, 1);
      const engagement = insights.engagement || (insights.likes + insights.comments + insights.saved + insights.shares);
      const engagementRate = Math.min(1, engagement / reach);

      totalReach += insights.reach;
      totalImpressions += insights.impressions;
      totalSaved += insights.saved;
      totalShares += insights.shares;
      totalInteractions += engagement;

      mediaPerformance.push({
        media,
        insights,
        engagementRate,
      });
    }

    // Ordena mídias por engajamento
    mediaPerformance.sort((a, b) => b.insights.engagement - a.insights.engagement);

    const averageEngagementRate =
      mediaPerformance.length > 0
        ? totalInteractions / Math.max(totalReach, 1)
        : 0;

    // Gera análise qualitativa e próximas pautas via LLM
    const performanceAnalysis = await this.llm.analyzePerformanceAndSuggest({
      reach: Math.max(totalReach, account.reach),
      impressions: Math.max(totalImpressions, account.impressions),
      engagementRate: averageEngagementRate,
      topPosts: mediaPerformance.slice(0, 3).map((m) => ({
        mediaId: m.media.id,
        engagement: m.insights.engagement,
        reach: m.insights.reach,
        caption: m.media.caption,
      })),
    });

    // Salva snapshot no banco para histórico
    const snapshotRecord: AnalyticsSnapshotRecord = {
      id: `analytics_${Date.now()}`,
      period,
      reach: totalReach,
      impressions: totalImpressions,
      profileViews: account.profileViews,
      followerCount: account.followerCount,
      topPosts: mediaPerformance.slice(0, 5).map((m) => ({
        mediaId: m.media.id,
        engagement: m.insights.engagement,
        reach: m.insights.reach,
      })),
      strategicSuggestions: performanceAnalysis.nextPautas.map((p) => p.title),
      recordedAt: new Date(),
    };
    await this.db.saveAnalyticsSnapshot(snapshotRecord);

    return {
      generatedAt: new Date(),
      period,
      account,
      mediaPerformance,
      totals: {
        totalReach,
        totalImpressions,
        totalSaved,
        totalShares,
        averageEngagementRate,
      },
      executiveSummary: performanceAnalysis.summary,
      keyInsights: performanceAnalysis.keyInsights,
      strategicPautas: performanceAnalysis.nextPautas,
    };
  }

  /**
   * Loop de retroalimentação: transforma as recomendações do Analytics
   * diretamente em rascunhos de pautas no Content Manager!
   */
  async feedbackToContentManager(): Promise<Array<{ title: string; postId?: string }>> {
    if (!this.contentManager) {
      throw new Error('ContentManagerAgent não foi fornecido para receber o feedback estratégico.');
    }

    const report = await this.generateReport('week');
    const createdPosts: Array<{ title: string; postId?: string }> = [];

    for (const pauta of report.strategicPautas) {
      try {
        const post = await this.contentManager.generatePost({
          type: 'PRICE_RANKING',
          angle: pauta.title,
        });
        createdPosts.push({ title: pauta.title, postId: post.id });
      } catch (err: any) {
        createdPosts.push({ title: pauta.title });
      }
    }

    return createdPosts;
  }

  /**
   * Formata o relatório em Markdown legível para compartilhamento ou logs
   */
  formatReportMarkdown(report: AnalyticsReport): string {
    const ratePercent = (report.totals.averageEngagementRate * 100).toFixed(2);
    return `
# 📊 Relatório Executivo de Performance Instagram - Imóvel Radar
**Período:** ${report.period} | **Gerado em:** ${report.generatedAt.toISOString()}

---

## 📈 Métricas Gerais
- **Alcance Total:** ${report.totals.totalReach.toLocaleString()}
- **Impressões Totais:** ${report.totals.totalImpressions.toLocaleString()}
- **Taxa Média de Engajamento:** ${ratePercent}%
- **Salvamentos:** ${report.totals.totalSaved}
- **Compartilhamentos:** ${report.totals.totalShares}
- **Visitas ao Perfil:** ${report.account.profileViews}
- **Seguidores:** ${report.account.followerCount}

---

## 💡 Resumo da IA
${report.executiveSummary}

### Destaques:
${report.keyInsights.map((k) => `- ${k}`).join('\n')}

---

## 🎯 Pautas Estratégicas Recomendadas (Feedback Loop)
${report.strategicPautas
  .map(
    (p, i) => `${i + 1}. **${p.title}** (${p.suggestedFormat})\n   *Motivo:* ${p.reason}`
  )
  .join('\n\n')}
`.trim();
  }
}
