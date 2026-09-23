import dotenv from 'dotenv';
import { DatabaseClient } from './infrastructure/database/client.js';
import { LLMService } from './infrastructure/ai/llm-service.js';
import { CardGenerator } from './infrastructure/renderer/card-generator.js';
import {
  createInstagramClient,
  MockInstagramClient,
} from './infrastructure/instagram/index.js';
import { ContentManagerAgent } from './agents/content-manager/index.js';
import { CommentAgent } from './agents/comment-agent/index.js';
import { AnalyticsAgent } from './agents/analytics-agent/index.js';

dotenv.config();

async function main() {
  const args = process.argv.slice(2);
  const command = args[0];
  const subcommand = args[1];

  const db = new DatabaseClient();
  const llm = new LLMService();
  const cardGenerator = new CardGenerator();
  const instagramClient = createInstagramClient();

  const contentManager = new ContentManagerAgent({
    db,
    llm,
    cardGenerator,
    instagramClient,
  });

  const commentAgent = new CommentAgent({
    db,
    llm,
    instagramClient,
    autoHideSpam: true,
    autoReply: true,
  });

  const analyticsAgent = new AnalyticsAgent({
    db,
    llm,
    instagramClient,
    contentManager,
  });

  console.log('🤖 Imóvel Radar — Instagram Bot CLI\n');

  try {
    if (command === 'content' && subcommand === 'generate') {
      console.log('📝 Gerando nova publicação para o Instagram...');
      const post = await contentManager.generatePost();
      console.log(`✅ Post criado com sucesso! [ID: ${post.id}]`);
      console.log(`📌 Título: ${post.title}`);
      console.log(`🖼️ Slides gerados: ${post.slides.length}`);
      console.log(`📋 Status: ${post.status}`);
      console.log(`\nLegenda:\n${post.caption}\n`);
      return;
    }

    if (command === 'content' && subcommand === 'publish') {
      console.log('🚀 Publicando último post criado...');
      const posts = await contentManager.listPosts('DRAFT');
      if (posts.length === 0) {
        console.log('⚠️ Nenhum post em DRAFT encontrado para publicar.');
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
      console.log('💬 Varrendo e processando comentários recentes...');
      const results = await commentAgent.processRecentPostsComments(3);
      console.log(`✅ ${results.length} comentários verificados.`);
      for (const r of results) {
        console.log(`   - @${r.username}: "${r.text}" -> [${r.analysis.intent}] ${r.actionTaken}`);
        if (r.replyText) console.log(`     Resposta: "${r.replyText}"`);
      }
      return;
    }

    if (command === 'analytics' && subcommand === 'report') {
      console.log('📊 Coletando métricas e gerando relatório executivo...');
      const report = await analyticsAgent.generateReport('week');
      console.log(analyticsAgent.formatReportMarkdown(report));
      return;
    }

    if (command === 'mock' && subcommand === 'comment') {
      if (!(instagramClient instanceof MockInstagramClient)) {
        console.log('⚠️ Simulação de comentário só está disponível no modo MOCK.');
        return;
      }
      const commentText = args.slice(2).join(' ') || 'ALERTA quero apê 2 quartos na Jatiúca!';
      const mediaList = await instagramClient.getRecentMedia(1);
      if (mediaList.length === 0) {
        console.log('⚠️ Nenhuma mídia encontrada para comentar.');
        return;
      }
      const targetMedia = mediaList[0];
      console.log(`🧪 Injetando comentário simulado no post ${targetMedia.id}...`);
      const comment = instagramClient.addMockComment(
        targetMedia.id,
        'usuario_simulado',
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
    console.log(`  pnpm run content:generate       Gera nova pauta, slides SVG e legenda`);
    console.log(`  pnpm run content:publish        Publica o post DRAFT mais recente`);
    console.log(`  pnpm run comments:process       Processa e modera comentários das mídias recentes`);
    console.log(`  pnpm run analytics:report       Gera relatório de engajamento e feedback loop`);
    console.log(`  pnpm run mock:simulate-comment  Injeta e responde comentário no mock\n`);
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
