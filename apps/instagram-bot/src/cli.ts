import fs from 'node:fs';
import dotenv from 'dotenv';
import { DatabaseClient } from './infrastructure/database/client.js';
import { LLMService } from './infrastructure/ai/llm-service.js';
import { createSocialClient } from './infrastructure/social/factory.js';
import { SocialPlatform } from './infrastructure/social/types.js';
import { CommentAgent } from './agents/comment-agent/index.js';
import { AnalyticsAgent } from './agents/analytics-agent/index.js';
import { LocalPublisher } from './agents/publisher/index.js';

dotenv.config();

function collectRepeatArgs(raw: string[], name: string): { values: string[]; rest: string[] } {
  const values: string[] = [];
  const rest: string[] = [];
  for (let i = 0; i < raw.length; i++) {
    const arg = raw[i];
    if (arg === name && raw[i + 1]) {
      values.push(raw[++i]);
    } else if (arg.startsWith(`${name}=`)) {
      values.push(arg.slice(name.length + 1));
    } else {
      rest.push(arg);
    }
  }
  return { values, rest };
}

function takeFlag(args: string[], name: string): string | undefined {
  const idx = args.indexOf(name);
  if (idx >= 0 && args[idx + 1]) {
    const value = args[idx + 1];
    args.splice(idx, 2);
    return value;
  }
  const prefixed = args.find((a) => a.startsWith(`${name}=`));
  if (prefixed) {
    args.splice(args.indexOf(prefixed), 1);
    return prefixed.slice(name.length + 1);
  }
  return undefined;
}

async function main() {
  const rawArgs = process.argv.slice(2);
  const filesResult = collectRepeatArgs(rawArgs, '--file');
  const urlsResult = collectRepeatArgs(filesResult.rest, '--url');
  const args = urlsResult.rest;

  const platform = (takeFlag(args, '--platform') || 'instagram').toLowerCase() as SocialPlatform;
  let caption = takeFlag(args, '--caption') || '';
  const captionFile = takeFlag(args, '--caption-file');
  if (captionFile) {
    caption = fs.readFileSync(captionFile, 'utf-8');
  }

  const command = args[0];
  const subcommand = args[1];

  const db = new DatabaseClient();
  const llm = new LLMService();
  const socialClient = createSocialClient(platform);
  const publisher = new LocalPublisher(socialClient);

  const commentAgent = new CommentAgent({
    db,
    llm,
    socialClient,
    autoHideSpam: true,
    autoReply: true,
  });

  const analyticsAgent = new AnalyticsAgent({
    db,
    llm,
    socialClient,
  });

  console.log(`🤖 Imóvel Radar — Social Bot CLI [Plataforma: ${platform.toUpperCase()}]\n`);

  try {
    if (command === 'publish') {
      console.log(`🚀 Publicando em ${platform.toUpperCase()}...`);
      const res = await publisher.publish({
        files: filesResult.values,
        urls: urlsResult.values,
        caption,
      });
      console.log('✅ Publicado.');
      console.log(`   Media ID: ${res.mediaId}`);
      if (res.permalink) console.log(`   Permalink: ${res.permalink}`);
      return;
    }

    if (command === 'comments' && subcommand === 'process') {
      console.log(`💬 Varrendo e processando comentários recentes no ${platform.toUpperCase()}...`);
      const results = await commentAgent.processRecentPostsComments(3);
      console.log(`✅ ${results.length} comentários verificados.`);
      for (const r of results) {
        console.log(`   - @${r.username}: "${r.text}" -> [${r.analysis.intent}] ${r.actionTaken}`);
        if (r.replyText) console.log(`     Resposta: "${r.replyText}"`);
      }
      return;
    }

    if (command === 'analytics' && subcommand === 'report') {
      console.log(`📊 Coletando métricas e gerando relatório executivo [${platform.toUpperCase()}]\n`);
      const report = await analyticsAgent.generateReport('week');
      console.log(analyticsAgent.formatReportMarkdown(report));
      return;
    }

    if (command === 'mock' && subcommand === 'comment') {
      if (typeof (socialClient as { addMockComment?: unknown }).addMockComment !== 'function') {
        console.log('⚠️ Simulação de comentário só está disponível no modo MOCK.');
        return;
      }
      const commentText = args.slice(2).join(' ') || 'ALERTA quero apê 2 quartos na Jatiúca!';
      const mediaList = await socialClient.getRecentMedia(1);
      if (mediaList.length === 0) {
        console.log('⚠️ Nenhuma mídia encontrada para comentar.');
        return;
      }
      const targetMedia = mediaList[0];
      console.log(`🧪 Injetando comentário simulado no post ${targetMedia.id} (${platform.toUpperCase()})...`);
      const comment = (
        socialClient as unknown as {
          addMockComment: (mediaId: string, user: string, text: string) => {
            id: string;
            mediaId: string;
            text: string;
            username: string;
            timestamp: string;
          };
        }
      ).addMockComment(targetMedia.id, `usuario_simulado_${platform}`, commentText);
      console.log(`📥 Comentário criado: "${comment.text}"`);

      console.log('⚡ Disparando CommentAgent...');
      const res = await commentAgent.processComment(comment, targetMedia.id);
      console.log(`✅ Ação executada: ${res.actionTaken}`);
      if (res.replyText) {
        console.log(`💬 Resposta enviada: "${res.replyText}"`);
      }
      return;
    }

    console.log('Publicação local (não gera conteúdo):\n');
    console.log('  publish --file ./foto.jpg --caption "texto"');
    console.log('  publish --file ./a.jpg --file ./b.jpg --caption "carrossel"');
    console.log('  publish --file ./video.mp4 --caption "reels"');
    console.log('  publish --platform tiktok --file ./video.mp4 --caption "tiktok"');
    console.log('  publish --url https://cdn.exemplo.com/foto.jpg --caption "já hospedada"\n');
    console.log('Outros:');
    console.log('  comments process       Modera comentários');
    console.log('  analytics report       Relatório');
    console.log('  mock comment           Comentário fake (MOCK)\n');
    console.log('Atalhos: pnpm run publish | comments:process | analytics:report');
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : String(err);
    console.error('❌ Erro na execução:', message);
    process.exit(1);
  } finally {
    await db.close();
  }
}

if (process.argv[1] && process.argv[1].endsWith('cli.ts')) {
  main();
}
