# Bot — Imóvel Radar

Bot Telegram do projeto. Em produção (serverless, ADR 0004/0005/0006) processa
webhooks do Telegram via API Gateway → Bot Lambda, com acesso direto ao Postgres
compartilhado (Neon) e estado de conversa em DynamoDB. O dev local segue usando
polling + PicklePersistence.

## Fluxos

- `/novo_alerta` — wizard de criação. Ao confirmar, escreve o alerta em
  `alerts` (dono: bot, ADR 0005), busca listings que casem e envia carrossel.
- **Meus Alertas** — listado, detalle e remoção leem/escritam `alerts`
  direto do banco.
- **Carrousel** — navegação Anterior/Próximo via `bot_data` persistido em
  DynamoDB (ADR 0006).
- **Notificação horária** — via EventBridge → Lambda: lista `users`, busca
  listings não notificados, envia carrossel e marca `alert_matches`.

## Configuração (`.env`)

```
TELEGRAM_BOT_TOKEN=123456:ABC-your-bot-token
ADMIN_CHAT_ID=123456789
LOG_LEVEL=INFO
DATABASE_URL=postgresql+psycopg://postgres:teste123@localhost:5432/imovel_radar
# Só para a Lambda/webhook (persistência DynamoDB, token via SSM):
DYNAMODB_TABLE=imovel-radar-prod-conversation-state
SSM_TOKEN_PARAM=/imovel-radar/prod/telegram_bot_token
```

## Como rodar (dev)

```bash
cd apps/bot
uv sync
# configure .env
uv run python main.py
```

## Arquitectura

```
apps/bot/
├── main.py                # dev: PTB polling + PicklePersistence
├── lambda_handler.py      # producão: webhook + notificação (ADR 0004)
├── application.py         # build_application + RadarApplication (ensure_user)
├── config.py              # config (token via env ou SSM)
├── models.py              # CustomContext, UserData, wizard types
├── persistence.py         # BasePersistence → DynamoDB (ADR 0006)
├── database/              # SQLModel: engine, models (mesmo schema do scraper)
│   ├── db.py              #   ADR 0005: acesso direto ao Postgres compartilhado
│   ├── models.py          #   Listing/User/Alert/AlertMatch
│   └── queries.py         #   CRUD de users/alerts/matches + matching
└── handlers/              # UI/conversa; dados via api_client (banco)
    ├── api_client.py      # camada de dados direto ao Postgres (ADR 0005)
    ├── setup.py           # registro de handlers
    └── ui/                # textos e teclados
```