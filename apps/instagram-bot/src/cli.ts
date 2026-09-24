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
  let postIdArg: string | undefined;
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
    } else if (arg === '--id' && rawArgs[i + 1]) {
      postIdArg = rawArgs[++i];
    } else if (arg.startsWith('--id=')) {
      postIdArg = arg.split('=')[1];
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
      console.log(`📝 Gerando rascunho para ${platform.toUpperCase()} (${format}) — não publica.`);
      const post = await contentManager.generatePost({ platform, format });
      console.log(`✅ Rascunho criado. Nada foi postado.`);
      console.log(`   ID: ${post.id}`);
      console.log(`   Título: ${post.title}`);
      console.log(`   Tipo: ${post.postType}${post.videoUrl ? ` (vídeo local)` : ''}`);
      console.log(`   Status: ${post.status}`);
      console.log('\nArquivos para você revisar:');
      for (const slide of post.slides) {
        if (slide.localPath) console.log(`   - slide ${slide.slideNumber}: ${slide.localPath}`);
      }
      if (post.videoUrl) console.log(`   - vídeo: ${post.videoUrl}`);
      console.log(`\nLegenda:\n${post.caption}\n`);
      console.log(
        `Se estiver ok:\n  pnpm run ${platform === 'tiktok' ? 'tiktok:publish' : 'content:publish'} -- --id ${post.id}`
      );
      return;
    }

    if (command === 'content' && subcommand === 'list') {
      const posts = await contentManager.listPosts(undefined, platform);
      if (posts.length === 0) {
        console.log(`Nenhum rascunho para ${platform}.`);
        return;
      }
      console.log(`Posts (${platform}):\n`);
      for (const post of posts) {
        console.log(`  [${post.status}] ${post.id}  ${post.postType}  ${post.title}`);
        const first = post.slides.find((s) => s.localPath)?.localPath;
        if (first) console.log(`           ${first}`);
      }
      console.log(`\nPublicar um rascunho: content publish --id <id> --platform ${platform}`);
      return;
    }

    if (command === 'content' && subcommand === 'publish') {
      const postId = postIdArg || cleanArgs[2];
      if (!postId) {
        const drafts = await contentManager.listPosts('DRAFT', platform);
        console.log('Informe o id do rascunho que você revisou. Nada foi publicado.');
        if (drafts.length > 0) {
          console.log('\nRascunhos disponíveis:');
          for (const post of drafts) {
            console.log(`  ${post.id}  ${post.title}`);
          }
          console.log(`\nExemplo: pnpm run content:publish -- --id ${drafts[0].id}`);
        } else {
          console.log('Nenhum DRAFT. Gere antes: pnpm run content:generate');
        }
        process.exitCode = 1;
        return;
      }
      console.log(`🚀 Publicando ${postId} em ${platform.toUpperCase()}...`);
      const res = await contentManager.publishPost(postId);
      console.log(`✅ Publicado.`);
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
    console.log(`Fluxo: gerar rascunho → você revisa os arquivos → publicar pelo id.\n`);
    console.log(`Comandos:`);
    console.log(`  content generate       Só gera (não posta). --platform tiktok --format video`);
    console.log(`  content list           Lista rascunhos`);
    console.log(`  content publish --id   Publica o rascunho que você validou`);
    console.log(`  comments process       Modera comentários`);
    console.log(`  analytics report       Relatório`);
    console.log(`  mock comment           Comentário fake (MOCK)\n`);
    console.log(`Atalhos: pnpm run content:generate | content:list | content:publish`);
    console.log(`         pnpm run tiktok:generate | tiktok:generate:video | tiktok:publish`);
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
