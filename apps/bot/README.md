# Bot — Imóvel Radar

Bot Telegram do projeto. Em produção (serverless, ADR 0004/0005/0006) processa
webhooks do Telegram via API Gateway → Bot Lambda, com acesso direto ao Postgres
compartilhado (Neon pooled) e estado de conversa em DynamoDB. O dev local segue
usando polling + PicklePersistence.

## Fluxos

- `/novo_alerta` — wizard persistente (`name="new_alert"`). Ao confirmar, escreve
  o alerta em `alerts` (idempotente nos filtros), busca matches e envia carrossel.
- **Meus Alertas** — listagem, detalhe e remoção leem/escrevem `alerts`.
- **Acompanhar anúncio** — até 2 listings (`watched_listings`); entrada pelo
  botão no carrossel de matches; notifica mudança de preço ou desativação.
- **Carrossel** — cards enxutos em `chat_data` (um item Dynamo por chat);
  navegação por índice no callback (`crs_{id}_{index}`) sem rewrite a cada
  clique; `file_id` do Telegram para fotos rápidas após a 1ª visita. TTL
  próprio (`CAROUSEL_TTL_HOURS`, default 7 dias), separado do wizard.
- **Notificação diária** — EventBridge (10:00 Maceió, 2h após o scrape) → Lambda
  (`run_daily_notifications`: matches + watchlist).

## Configuração (`.env`)

```
TELEGRAM_BOT_TOKEN=123456:ABC-your-bot-token
ADMIN_CHAT_ID=123456789
LOG_LEVEL=INFO
DATABASE_URL=postgresql+psycopg://postgres:teste123@localhost:5432/imovel_radar
# Lambda/webhook:
DYNAMODB_TABLE=imovel-radar-prod-conversation-state
SSM_TOKEN_PARAM=/imovel-radar/prod/telegram_bot_token
TELEGRAM_WEBHOOK_SECRET=...
```

## Como rodar (dev)

```bash
cd apps/bot
uv sync
uv run python main.py
```

## Arquitetura

```
apps/bot/
├── main.py                # dev: PTB polling + PicklePersistence
├── lambda_handler.py      # produção: webhook + notificação
├── application.py         # build_application + RadarApplication
├── persistence.py         # BasePersistence → DynamoDB
├── database/              # engine lazy + queries
└── handlers/
    ├── data.py            # camada de dados (Postgres)
    ├── setup.py
    └── ui/
```
