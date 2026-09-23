# Imóvel Radar — Instagram Bot 📸🤖

Aplicação multi-agente desenvolvida em TypeScript/Node.js para automação de conteúdo, moderação inteligente de comentários e análise estratégica de performance no Instagram do **Imóvel Radar Maceió**.

---

## 🏛️ Os 3 Agentes

### 1. ✍️ Content Manager Agent
- **Geração de Pautas**: Analisa em tempo real os dados de `market_snapshot` e `listing` (preço mediano por m², ranking de bairros de Maceió como Ponta Verde, Jatiúca, Pajuçara, quedas de preço e novas oportunidades).
- **Copywriting**: Cria títulos chamativos, ganchos (hooks) de retenção, roteiros de carrossel, legendas completas com hashtags e CTA focado em conversão.
- **Renderizador Visual**: Produz slides SVG limpos e formatados para Instagram (1080x1350 portrait 4:5 ou 1080x1080).
- **Fila e Agendamento**: Gerencia ciclo de vida dos posts (`DRAFT` → `APPROVED` → `SCHEDULED` → `PUBLISHED`).

### 2. 💬 Comment Agent
- **Classificação de Intenção com IA**:
  - `ALERT_REQUEST`: Usuários pedindo alertas ou links de imóveis → responde automaticamente direcionando para o bot Telegram (`@imovelradar_bot`).
  - `PRICE_QUERY`: Dúvidas sobre preço mediano e condomínio em bairros de Maceió.
  - `GENERAL_ENGAGEMENT`: Reações, dúvidas ou elogios ao conteúdo.
  - `SPAM`: Detecção automática de links maliciosos, propostas de renda extra e compra de seguidores.
- **Moderação Ativa**: Oculta spam automaticamente (`hideComment`) e registra auditoria completa de cada interação.
- **Idempotência**: Garante que nenhum comentário seja respondido mais de uma vez.

### 3. 📊 Analytics Agent
- **Coleta de Métricas**: Alcance, impressões, salvamentos, compartilhamentos, taxa de engajamento e visitas ao perfil.
- **Relatório Executivo**: Síntese de desempenho formatada em Markdown ou JSON.
- **Feedback Loop**: Identifica os temas e bairros que geraram maior engajamento e gera automaticamente novas pautas recomendadas para o **Content Manager**.

---

## 🔌 Camada de Adaptador: Mock vs Meta Graph API

A aplicação utiliza o padrão **Adapter** (`InstagramClient`), permitindo alternar via `.env`:

- `INSTAGRAM_MODE=MOCK`:
  - Não requer conta da Meta nem tokens.
  - Persiste publicações, comentários simulados e métricas em arquivos locais.
  - Ideal para desenvolvimento local, testes automatizados e demonstrações.
- `INSTAGRAM_MODE=LIVE`:
  - Integração oficial com a **Meta Graph API v21+** (`/media`, `/media_publish`, `/comments`, `/insights`).
  - Publicação de carrosséis oficiais com contêineres e suporte a rate limits.

---

## 🚀 Como Usar

### 1. Instalação e Configuração
```bash
# Na raiz do monorepo
pnpm install

# Configurar variáveis de ambiente do instagram-bot
cp apps/instagram-bot/.env.example apps/instagram-bot/.env
```

### 2. Comandos CLI
```bash
# Gerar nova pauta com carrossel SVG e legenda completa
pnpm run content:generate

# Publicar o post em DRAFT mais recente
pnpm run content:publish

# Processar comentários pendentes nas mídias recentes
pnpm run comments:process

# Injetar comentário simulado e testar a resposta do CommentAgent
pnpm run mock:simulate-comment

# Gerar relatório de métricas e sugestões estratégicas
pnpm run analytics:report
```

### 3. Servidor Webhook (Meta Graph API)
```bash
# Iniciar servidor HTTP
pnpm --filter instagram-bot start
```
- `GET /health`: Healthcheck do serviço.
- `GET /webhook`: Endpoint de verificação de token (`hub.challenge`) da Meta.
- `POST /webhook`: Receptor de eventos em tempo real da Meta para comentários do Instagram.
- `POST /api/content/generate`: Disparo manual de criação de conteúdo.
- `GET /api/analytics/report`: Extração do relatório de performance.

---

## 🧪 Testes Automatizados
```bash
pnpm --filter instagram-bot test
```
A suíte do `vitest` cobre:
- Ciclo de vida do `MockInstagramClient` (posts, carrosséis, respostas, spam, insights);
- Acesso a dados de mercado e renderização SVG (`CardGenerator`);
- Classificação e geração contextual com IA (`LLMService`);
- Fluxo completo do `ContentManagerAgent`;
- Resposta e moderação do `CommentAgent`;
- Análise e feedback loop do `AnalyticsAgent`;
- Endpoints HTTP e verificação de webhook da Meta (`server.ts`).
