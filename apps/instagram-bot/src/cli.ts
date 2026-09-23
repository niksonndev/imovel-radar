import dotenv from 'dotenv';
import { DatabaseClient } from './infrastructure/database/client.js';
import { LLMService } from './infrastructure/ai/llm-service.js';
import { CardGenerator } from './infrastructure/renderer/card-generator.js';
import { VideoSlideshowGenerator } from './infrastructure/renderer/video-slideshow.js';
import { createSocialClient } from './infrastructure/social/factory.js';
import { SocialPlatform } from './infrastructure/social/types.js';
import { ContentManagerAgent } from './agents/content-manager/index.js';
import { CommentAgent } from './agents/comment-agent/index.js';
import { AnalyticsAgent } from './agents/analytics-agent/index.js';

dotenv.config();

async function main() {
  const rawArgs = process.argv.slice(2);
  let platform: SocialPlatform = 'instagram';
  let format: 'photo' | 'video' = 'photo';
  const cleanArgs: string[] = [];

  for (let i = 0; i < rawArgs.length; i++) {
    const arg = rawArgs[i];
    if (arg === '--platform' && rawArgs[i + 1]) {
      platform = rawArgs[++i].toLowerCase() as SocialPlatform;
    } else if (arg.startsWith('--platform=')) {
      platform = arg.split('=')[1].toLowerCase() as SocialPlatform;
    } else if (arg === '--format' && rawArgs[i + 1]) {
      format = rawArgs[++i].toLowerCase() as 'photo' | 'video';
    } else if (arg.startsWith('--format=')) {
      format = arg.split('=')[1].toLowerCase() as 'photo' | 'video';
    } else {
      cleanArgs.push(arg);
    }
  }

  const command = cleanArgs[0];
  const subcommand = cleanArgs[1];

  const db = new DatabaseClient();
  const llm = new LLMService();
  const cardGenerator = new CardGenerator();
  const videoGenerator = new VideoSlideshowGenerator();
  const socialClient = createSocialClient(platform);

  const contentManager = new ContentManagerAgent({
    db,
    llm,
    cardGenerator,
    videoGenerator,
    socialClient,
  });

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
    contentManager,
  });

  console.log(`🤖 Imóvel Radar — Social Bot CLI [Plataforma: ${platform.toUpperCase()}]\n`);

  try {
    if (command === 'content' && subcommand === 'generate') {
      console.log(`📝 Gerando nova publicação para ${platform.toUpperCase()} (${format})...`);
      const post = await contentManager.generatePost({ platform, format });
      console.log(`✅ Post criado com sucesso! [ID: ${post.id}]`);
      console.log(`📌 Título: ${post.title}`);
      console.log(`🖼️ Slides gerados: ${post.slides.length}`);
      console.log(`🎬 Tipo: ${post.postType}${post.videoUrl ? ` (Vídeo: ${post.videoUrl})` : ''}`);
      console.log(`📋 Status: ${post.status}`);
      console.log(`\nLegenda:\n${post.caption}\n`);
      return;
    }

    if (command === 'content' && subcommand === 'publish') {
      console.log(`🚀 Publicando último post criado para ${platform.toUpperCase()}...`);
      const posts = await contentManager.listPosts('DRAFT', platform);
      if (posts.length === 0) {
        console.log(`⚠️ Nenhum post em DRAFT encontrado para ${platform.toUpperCase()}.`);
        return;
      }
      const target = posts[0];
      const res = await contentManager.publishPost(target.id);
      console.log(`✅ Post publicado com sucesso!`);
      console.log(`   - Media ID: ${res.mediaId}`);
      if (res.permalink) console.log(`   - Permalink: ${res.permalink}`);
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
      console.log(`📊 Coletando métricas e gerando relatório executivo [${platform.toUpperCase()}]...`);
      const report = await analyticsAgent.generateReport('week');
      console.log(analyticsAgent.formatReportMarkdown(report));
      return;
    }

    if (command === 'mock' && subcommand === 'comment') {
      if (typeof (socialClient as any).addMockComment !== 'function') {
        console.log(`⚠️ Simulação de comentário só está disponível no modo MOCK.`);
        return;
      }
      const commentText = cleanArgs.slice(2).join(' ') || 'ALERTA quero apê 2 quartos na Jatiúca!';
      const mediaList = await socialClient.getRecentMedia(1);
      if (mediaList.length === 0) {
        console.log('⚠️ Nenhuma mídia encontrada para comentar.');
        return;
      }
      const targetMedia = mediaList[0];
      console.log(`🧪 Injetando comentário simulado no post ${targetMedia.id} (${platform.toUpperCase()})...`);
      const comment = (socialClient as any).addMockComment(
        targetMedia.id,
        `usuario_simulado_${platform}`,
        commentText
      );
      console.log(`📥 Comentário criado: "${comment.text}"`);

      console.log('⚡ Disparando CommentAgent...');
      const res = await commentAgent.processComment(comment, targetMedia.id);
      console.log(`✅ Ação executada: ${res.actionTaken}`);
      if (res.replyText) {
        console.log(`💬 Resposta enviada: "${res.replyText}"`);
      }
      return;
    }

    // Default / Help
    console.log(`Comandos disponíveis:`);
    console.log(`  pnpm run content:generate       Gera nova pauta, slides SVG e legenda (use --platform tiktok --format video)`);
    console.log(`  pnpm run content:publish        Publica o post DRAFT mais recente`);
    console.log(`  pnpm run comments:process       Processa e modera comentários das mídias recentes`);
    console.log(`  pnpm run analytics:report       Gera relatório de engajamento e feedback loop`);
    console.log(`  pnpm run mock:simulate-comment  Injeta e responde comentário no mock`);
    console.log(`\nOpções:`);
    console.log(`  --platform instagram|tiktok     Seleciona a rede social (padrão: instagram)`);
    console.log(`  --format photo|video            Seleciona o formato para TikTok (padrão: photo)\n`);
  } catch (err: any) {
    console.error('❌ Erro na execução:', err.message || err);
    process.exit(1);
  } finally {
    await db.close();
  }
}

if (process.argv[1] && process.argv[1].endsWith('cli.ts')) {
  main();
}
