# Docker — Imóvel Radar (dev local)

Containerização do scraper (health) e do bot (polling) **só para desenvolvimento**
via `docker-compose.yml`. **Produção é serverless (Lambda)** — ver
`.github/workflows/infra-deploy.yml`. O arquivo `docker-compose.prod.yml` está
aposentado e não define serviços.

## Pré-requisitos

- Docker Engine com Compose v2
- `.env` locais:

  ```bash
  cp apps/scraper/.env.example apps/scraper/.env
  cp apps/bot/.env.example apps/bot/.env
  ```

  `apps/bot/.env` precisa de `TELEGRAM_BOT_TOKEN` e `DATABASE_URL` (mesmo Postgres
  do scraper). O compose injeta `DATABASE_URL` apontando para o host.

## Como subir

```bash
docker compose up --build -d
docker compose ps
```

- Scraper: `http://localhost:8000/health`
- Bot: polling Telegram (sem porta exposta); persiste pickle em `bot_state`

## Produção

Deploy canônico: `.github/workflows/infra-deploy.yml` (scraper Lambda + bot Lambda
+ API Gateway webhook + EventBridge + setWebhook).

Não há host Compose em produção. O workflow `docker-images.yml` (GHCR) é opcional
(rollback/dev) e **não** alimenta o runtime produtivo.
