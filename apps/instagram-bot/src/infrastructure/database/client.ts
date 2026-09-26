import fs from 'node:fs';
import path from 'node:path';
import { SocialPlatform } from '../social/types.js';

export interface CommentLogRecord {
  id: string;
  platform?: SocialPlatform;
  commentId: string;
  mediaId: string;
  username: string;
  commentText: string;
  intent: 'ALERT_REQUEST' | 'PRICE_QUERY' | 'GENERAL_ENGAGEMENT' | 'SPAM';
  replyText?: string;
  repliedAt?: Date;
  hidden: boolean;
}

export interface AnalyticsSnapshotRecord {
  id: string;
  platform?: SocialPlatform;
  period: string;
  reach: number;
  impressions: number;
  profileViews: number;
  followerCount: number;
  topPosts: Array<{
    mediaId: string;
    engagement: number;
    reach: number;
  }>;
  strategicSuggestions: string[];
  recordedAt: Date;
}

export class DatabaseClient {
  private inMemoryComments: CommentLogRecord[] = [];
  private inMemoryAnalytics: AnalyticsSnapshotRecord[] = [];
  private stateFilePath: string;

  constructor(_connectionString?: string, stateStoragePath?: string) {
    this.stateFilePath =
      stateStoragePath ||
      path.resolve(process.cwd(), '.bot-database-state.json');
    this.loadStateFromFile();
  }

  private loadStateFromFile(): void {
    try {
      if (fs.existsSync(this.stateFilePath)) {
        const raw = fs.readFileSync(this.stateFilePath, 'utf-8');
        const parsed = JSON.parse(raw);
        if (Array.isArray(parsed.comments)) {
          this.inMemoryComments = parsed.comments.map((c: CommentLogRecord & { repliedAt?: string }) => ({
            ...c,
            platform: c.platform || 'instagram',
            repliedAt: c.repliedAt ? new Date(c.repliedAt) : undefined,
          }));
        }
        if (Array.isArray(parsed.analytics)) {
          this.inMemoryAnalytics = parsed.analytics.map(
            (a: AnalyticsSnapshotRecord & { recordedAt: string }) => ({
              ...a,
              platform: a.platform || 'instagram',
              recordedAt: new Date(a.recordedAt),
            })
          );
        }
      }
    } catch {
      // Ignora erro de leitura
    }
  }

  private saveStateToFile(): void {
    try {
      const data = {
        comments: this.inMemoryComments,
        analytics: this.inMemoryAnalytics,
      };
      fs.writeFileSync(this.stateFilePath, JSON.stringify(data, null, 2), 'utf-8');
    } catch {
      // Ignora erro de escrita
    }
  }

  async logCommentInteraction(log: CommentLogRecord): Promise<void> {
    this.inMemoryComments.push({
      ...log,
      platform: log.platform || 'instagram',
    });
    this.saveStateToFile();
  }

  async getCommentLogs(platform?: SocialPlatform): Promise<CommentLogRecord[]> {
    if (!platform) return [...this.inMemoryComments];
    return this.inMemoryComments.filter((c) => (c.platform || 'instagram') === platform);
  }

  async saveAnalyticsSnapshot(snapshot: AnalyticsSnapshotRecord): Promise<void> {
    this.inMemoryAnalytics.unshift({
      ...snapshot,
      platform: snapshot.platform || 'instagram',
    });
    this.saveStateToFile();
  }

  async getRecentAnalytics(limit = 10, platform?: SocialPlatform): Promise<AnalyticsSnapshotRecord[]> {
    const list = platform
      ? this.inMemoryAnalytics.filter((a) => (a.platform || 'instagram') === platform)
      : this.inMemoryAnalytics;
    return list.slice(0, limit);
  }

  async close(): Promise<void> {
    // Estado é só arquivo local
  }
}
