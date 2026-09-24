# Imóvel Radar — Social Bot (Instagram & TikTok) 📸🎵🤖

Aplicação multi-agente desenvolvida em TypeScript/Node.js para automação de conteúdo, moderação inteligente de comentários e análise estratégica de performance multiplataforma (**Instagram** e **TikTok**) do **Imóvel Radar Maceió**.

---

## 🏛️ Os 3 Agentes Multiplataforma

A aplicação é orquestrada através da abstração compartilhada `SocialClient` com detecção de capacidades (`SocialCapabilities`), operando tanto no Instagram quanto no TikTok:

### 1. ✍️ Content Manager Agent
- **Geração de Pautas**: Analisa em tempo real os dados de `market_snapshot` e `listing` (preço mediano por m², ranking de bairros de Maceió como Ponta Verde, Jatiúca, Pajuçara, quedas de preço e novas oportunidades).
- **Copywriting Contextual com IA**:
  - **Instagram**: Carrosséis educativos 4:5 (1080x1350), chamadas para arrastar para o lado, legendas analíticas e hashtags regionais.
  - **TikTok**: Formato vertical 9:16 (1080x1920), títulos curtos (max 90 caracteres para a API do TikTok), linguagem dinâmica com hashtags virais (`#fyp`, `#tiktokimoveis`, `#maceio`), chamada para deslizar ("Deslize 📲") e CTA direcionado.
- **Renderizador Visual & Pipeline de Mídia**:
  - **Photo Mode (Padrão TikTok)**: Slides verticais 9:16 rasterizados de SVG para PNG de alta fidelidade com `@resvg/resvg-js`.
  - **Vídeo Slideshow (`--format video`)**: Pipeline automatizado com `ffmpeg` que compila os slides PNG em um vídeo MP4 vertical (1080x1920) a 30fps com duração configurável por slide (~3s).
- **Fila e Agendamento**: Gerencia ciclo de vida dos posts (`DRAFT` → `APPROVED` → `SCHEDULED` → `PUBLISHED`) com suporte a `CAROUSEL`, `SINGLE_IMAGE` e `VIDEO`.

### 2. 💬 Comment Agent
- **Classificação de Intenção com IA**:
  - `ALERT_REQUEST`: Usuários pedindo alertas ou links de imóveis → responde automaticamente direcionando para o bot Telegram (`@imovelradar_bot`).
  - `PRICE_QUERY`: Dúvidas sobre preço mediano e condomínio em bairros de Maceió.
  - `GENERAL_ENGAGEMENT`: Reações, dúvidas ou elogios ao conteúdo.
  - `SPAM`: Detecção automática de links maliciosos, propostas de renda extra e compra de seguidores.
- **Moderação Ativa & Respeito a Capabilities**:
  - Oculta spam (`hideComment`) e envia respostas automáticas (`replyComment`) quando a plataforma suporta.
  - No TikTok LIVE, onde a API de criador não oferece moderação ativa como a Meta, o agente detecta `capabilities.replyComment = false` e registra no log com segurança sem falhas.
- **Idempotência**: Garante que nenhum comentário seja respondido mais de uma vez.

### 3. 📊 Analytics Agent
- **Coleta e Normalização de Métricas**:
  - Instagram: Alcance, impressões, engajamento, salvamentos, compartilhamentos e visitas ao perfil.
  - TikTok: Mapeia `view_count` para visualizações/impressões, e soma `like_count`, `comment_count` e `share_count` para a taxa de engajamento.
- **Relatório Executivo**: Síntese de desempenho formatada em Markdown ou JSON com segmentação por plataforma.
- **Feedback Loop**: Identifica os temas, formatos e bairros que geraram maior engajamento e gera automaticamente novas pautas recomendadas para o **Content Manager**.

---

## 🔌 Padrão Adapter: MOCK vs LIVE

Tanto o Instagram quanto o TikTok operam sob o padrão **Adapter** com alternância transparente via `.env`:

### Instagram (`INSTAGRAM_MODE=MOCK|LIVE`)
- **MOCK**: Estado simulado em `.mock-instagram-state.json`. Ideal para desenvolvimento local e testes.
- **LIVE**: Meta Graph API **v26.0** (`/media` → espera `FINISHED` → `/media_publish`, comentários, insights). Host `graph.facebook.com` (Facebook Login) ou `graph.instagram.com` (Instagram Login).

### TikTok (`TIKTOK_MODE=MOCK|LIVE`)
- **MOCK**: Estado simulado em `.mock-tiktok-state.json`. Suporta ciclo completo de post foto, carrossel photo mode, vídeo slideshow, moderação de comentários e métricas.
- **LIVE**: Integração com a **TikTok Content Posting API v2**:
  - **Photo Mode**: `POST /v2/post/publish/content/init/` com `media_type: PHOTO` e `post_mode: DIRECT_POST`.
  - **Vídeo**: `POST /v2/post/publish/video/init/` via `PULL_FROM_URL`.
  - **Métricas**: `POST /v2/video/list/` com campos de performance.
  - **Requisitos TikTok LIVE**:
    - Escopos de aplicativo: `video.publish` e `video.list`.
    - Domínio verificado: as mídias servidas via `SITE_BASE_URL` devem estar em domínio verificado no portal de desenvolvedores do TikTok.
    - Nível de privacidade inicial: `TIKTOK_PRIVACY_LEVEL=SELF_ONLY` (recomendado até aprovação do aplicativo pela equipe do TikTok).

---

## ⚙️ Variáveis de Ambiente (`.env`)

```env
# Modo das Plataformas (MOCK ou LIVE)
INSTAGRAM_MODE=MOCK
TIKTOK_MODE=MOCK

# TikTok API (para TIKTOK_MODE=LIVE)
TIKTOK_CLIENT_KEY=seu_client_key
TIKTOK_CLIENT_SECRET=seu_client_secret
TIKTOK_ACCESS_TOKEN=seu_access_token_tiktok
TIKTOK_PRIVACY_LEVEL=SELF_ONLY # SELF_ONLY, MUTUAL_FOLLOW_FRIENDS, FOLLOWER_OF_CREATOR, PUBLIC_TO_EVERYONE

# Meta / Instagram Graph API
META_APP_ID=
META_APP_SECRET=
META_ACCESS_TOKEN=
INSTAGRAM_ACCOUNT_ID=
INSTAGRAM_ACCESS_TOKEN=
GRAPH_API_VERSION=v26.0
GRAPH_API_HOST=graph.facebook.com
META_VERIFY_TOKEN=imovel_radar_verify_token_secret

# LLM (OpenAI recomendado para geração contextual por rede)
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini
TELEGRAM_BOT_USERNAME=imovelradar_bot
SITE_BASE_URL=https://imovel-radar.onrender.com
PORT=3000
```

---

## 🚀 Como Usar

### 1. Comandos CLI — Instagram (gerar → revisar → publicar)
```bash
# Só gera rascunho (slides em generated-media/, status DRAFT — não posta)
pnpm run content:generate

# Lista rascunhos
pnpm run content:list

# Publica o id que você revisou
pnpm run content:publish -- --id post_...
```

# Processar comentários do Instagram
pnpm run comments:process

# Simular comentário no mock do Instagram
pnpm run mock:simulate-comment

# Relatório de analytics do Instagram
pnpm run analytics:report
```

### 2. Comandos CLI — TikTok
```bash
# Gerar carrossel Photo Mode 9:16 (rascunho)
pnpm run tiktok:generate

# Gerar vídeo slideshow 9:16 (rascunho)
pnpm run tiktok:generate:video

# Publicar o rascunho revisado
pnpm run tiktok:publish -- --id post_...

# Processar comentários do TikTok
pnpm run tiktok:comments

# Simular comentário no mock do TikTok
pnpm run tiktok:simulate-comment

# Relatório de analytics do TikTok
pnpm run tiktok:analytics
```

### 3. Servidor Webhook & API HTTP
```bash
# Iniciar servidor HTTP (porta configurável, bind 0.0.0.0 para Render)
pnpm --filter instagram-bot start
```
- `GET /health`: Informa o status do serviço e plataformas ativas (`['instagram', 'tiktok']`).
- `GET /webhook`: Endpoint de verificação de token (`hub.challenge`) da Meta.
- `POST /webhook`: Receptor de eventos de comentários da Meta.
- `GET /webhook/tiktok`: Verificação do webhook da TikTok Content Posting API.
- `POST /webhook/tiktok`: Receptor de eventos de status de publicação do TikTok.
- `POST /api/content/generate`: Disparo manual aceitando `{ platform: "tiktok"|"instagram", format: "photo"|"video" }`.
- `GET /api/analytics/report?platform=tiktok`: Extração do relatório de performance segmentado.

---

## 🧪 Testes Automatizados
```bash
pnpm --filter instagram-bot test
```
A suíte do `vitest` cobre:
- Ciclo de vida do `MockInstagramClient` (posts, carrosséis, respostas, spam, insights);
- Ciclo de vida do `MockTikTokClient` (posts simples, photo mode, vídeo slideshow, moderação, insights);
- Renderizador visual SVG 4:5 e 9:16 com rasterização PNG (`CardGenerator`);
- Compilador de vídeo slideshow com `ffmpeg` (`VideoSlideshowGenerator`);
- Classificação e copywriting contextualizado por plataforma com IA (`LLMService`);
- Geração e publicação de posts nos três formatos pelo `ContentManagerAgent`;
- Moderação idempotente de comentários pelo `CommentAgent` em ambas as plataformas;
- Agregação de métricas e feedback loop pelo `AnalyticsAgent`;
- Endpoints HTTP e webhooks para Meta e TikTok (`server.ts`).
