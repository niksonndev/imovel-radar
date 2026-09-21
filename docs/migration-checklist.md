# Migration checklist — Bot Lambda (acesso direto ao Postgres)

> Contexto: migração do bot para o modelo serverless (ADR 0004), com o bot
> como dono de `users`/`alerts`/`alert_matches` e leitura direta de `listing`
> no Postgres compartilhado (ADR 0005) e estado de conversa em DynamoDB
> (ADR 0006). O scraper não entra neste escopo — collector já funcionando.

## Fase 1

- [x] Remover dependência de `shared_models.api_schemas` no bot
- [x] Testes do bot: `database/queries.py`, `persistence.py`, smoke do `lambda_handler.py`

## Fase 2

- [x] Secret do webhook (`X-Telegram-Bot-Api-Secret-Token` + `setWebhook`)
- [x] Connection string pooled do Neon (check no CI + warning no engine)
- [x] `post_init` via Application builder em `main.py`
- [x] Transação unificada (commit no chamador; `ensure_user` não commita internamente)
- [x] Engine lazy em `database/db.py`
- [x] Rename `handlers/api_client.py` → `handlers/data.py`
- [x] Typo `"Schenduled Event"`; espanhol no `.env.example`
- [x] Guidelines/docs do monorepo alinhados ao ADR 0005

## Fase 3 — Deploy

- [x] Pipeline: testes (scraper + bot) → zips → alembic → terraform → setWebhook (`secret_token`, `-raw`)
- [ ] Smoke humano pós-deploy: mensagem real, wizard completo (incl. cold start), notify, logs
- [x] Produção = só Lambda (`docker-compose.prod.yml` aposentado; sem host Compose)

## Fase 4 — Backlog

- [x] Remover endpoints users/alerts/matches da API do scraper
- [x] `shared_models.api_schemas` deprecated (não reexportado)
- [x] Idempotência do confirm do wizard (draft `created_alert_id` + `find_equivalent_alert`)
