import { DatabaseClient, CommentLogRecord } from '../../infrastructure/database/client.js';
import { LLMService, CommentAnalysis } from '../../infrastructure/ai/llm-service.js';
import { SocialClient, SocialComment } from '../../infrastructure/social/types.js';

export interface CommentAgentOptions {
  db: DatabaseClient;
  llm: LLMService;
  instagramClient?: SocialClient;
  socialClient?: SocialClient;
  autoHideSpam?: boolean;
  autoReply?: boolean;
}

export interface ProcessedCommentResult {
  commentId: string;
  mediaId: string;
  username: string;
  text: string;
  analysis: CommentAnalysis;
  actionTaken: 'REPLIED' | 'HIDDEN' | 'IGNORED' | 'SKIPPED_ALREADY_HANDLED';
  replyText?: string;
}

export class CommentAgent {
  private db: DatabaseClient;
  private llm: LLMService;
  private socialClient: SocialClient;
  private autoHideSpam: boolean;
  private autoReply: boolean;
  private processedCommentIds: Set<string> = new Set();

  constructor(options: CommentAgentOptions) {
    this.db = options.db;
    this.llm = options.llm;
    const client = options.socialClient || options.instagramClient;
    if (!client) {
      throw new Error('CommentAgent requer socialClient ou instagramClient');
    }
    this.socialClient = client;
    this.autoHideSpam = options.autoHideSpam ?? true;
    this.autoReply = options.autoReply ?? true;
  }

  get instagramClient(): SocialClient {
    return this.socialClient;
  }

  /**
   * Processa um comentário recebido (por polling ou por webhook em tempo real)
   */
  async processComment(
    comment: SocialComment,
    mediaId: string
  ): Promise<ProcessedCommentResult> {
    if (this.processedCommentIds.has(comment.id) || (comment.replies && comment.replies.length > 0)) {
      return {
        commentId: comment.id,
        mediaId,
        username: comment.username,
        text: comment.text,
        analysis: {
          intent: 'GENERAL_ENGAGEMENT',
          confidence: 1,
          suggestedReply: '',
          shouldHide: false,
          reason: 'Comentário já respondido ou processado anteriormente.',
        },
        actionTaken: 'SKIPPED_ALREADY_HANDLED',
      };
    }

    // 1. Análise e Classificação com LLM
    const analysis = await this.llm.classifyComment(comment.text);

    let actionTaken: ProcessedCommentResult['actionTaken'] = 'IGNORED';
    let replyText: string | undefined;

    // 2. Se for SPAM e autoHide ativo -> oculta o comentário
    if (analysis.intent === 'SPAM' && analysis.shouldHide && this.autoHideSpam) {
      if (this.socialClient.capabilities.hideComment) {
        await this.socialClient.hideComment(comment.id);
        actionTaken = 'HIDDEN';
      } else {
        actionTaken = 'IGNORED';
      }
    } else if (this.autoReply && analysis.suggestedReply) {
      // 3. Responde comentários legítimos
      if (this.socialClient.capabilities.replyComment) {
        await this.socialClient.replyComment(comment.id, analysis.suggestedReply);
        actionTaken = 'REPLIED';
        replyText = analysis.suggestedReply;
      } else {
        actionTaken = 'IGNORED';
      }
    }

    // 4. Marca como processado
    this.processedCommentIds.add(comment.id);

    // 5. Registra log para auditoria e histórico
    const log: CommentLogRecord = {
      id: `comment_log_${Date.now()}_${Math.random().toString(36).substring(2, 6)}`,
      platform: this.socialClient.platform,
      commentId: comment.id,
      mediaId,
      username: comment.username,
      commentText: comment.text,
      intent: analysis.intent,
      replyText,
      repliedAt: actionTaken === 'REPLIED' ? new Date() : undefined,
      hidden: actionTaken === 'HIDDEN',
    };
    await this.db.logCommentInteraction(log);

    return {
      commentId: comment.id,
      mediaId,
      username: comment.username,
      text: comment.text,
      analysis,
      actionTaken,
      replyText,
    };
  }

  /**
   * Varre e processa todos os comentários de uma mídia específica
   */
  async processMediaComments(mediaId: string): Promise<ProcessedCommentResult[]> {
    const comments = await this.socialClient.getComments(mediaId);
    const results: ProcessedCommentResult[] = [];

    for (const comment of comments) {
      // Pula comentários já marcados como ocultos
      if (comment.hidden) continue;

      const res = await this.processComment(comment, mediaId);
      results.push(res);
    }

    return results;
  }

  /**
   * Varre os posts mais recentes da conta e modera novos comentários
   */
  async processRecentPostsComments(limit = 3): Promise<ProcessedCommentResult[]> {
    const recent = await this.socialClient.getRecentMedia(limit);
    const allResults: ProcessedCommentResult[] = [];

    for (const item of recent) {
      const results = await this.processMediaComments(item.id);
      allResults.push(...results);
    }

    return allResults;
  }

  async getLogs(): Promise<CommentLogRecord[]> {
    return this.db.getCommentLogs(this.socialClient.platform);
  }
}
