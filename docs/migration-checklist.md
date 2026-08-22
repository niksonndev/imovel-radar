# Migration checklist — Bot Lambda (acesso direto ao Postgres)

> Contexto: migração do bot para o modelo serverless (ADR 0004), com o bot
> como dono de `users`/`alerts`/`alert_matches` e leitura direta de `listing`
> no Postgres compartilhado (ADR 0005) e estado de conversa em DynamoDB
> (ADR 0006). O scraper não entra neste escopo — collector já funcionando.

## Fase 1 — Em progresso

- [ ] Remover import residual de `NotifiedPair` (`shared_models.api_schemas`)
      em `apps/bot/jobs/polling_job.py`
- [ ] Adicionar testes ao bot (hoje: zero cobertura; CI roda só `ruff`)
      - unitários para `database/queries.py`
      - unitários para `persistence.py` (DynamoDBPersistence)
      - smoke test do `lambda_handler.py`

## Fase 2 — Endurecimento

- [ ] Secret do webhook: pendência de implementação — validar o header
      `X-Telegram-Bot-Api-Secret-Token` no `lambda_handler` e configurar o
      `secret_token` no `setWebhook` (hoje qualquer um que descobrir a URL do
      API Gateway consegue injetar updates falsos)
- [ ] Garantir uso da connection string *pooled* do Neon na Lambda
- [ ] Revisar hack `app.post_init = post_init` em `main.py` (usar builder)
- [ ] Unificar semântica de transação nas queries (commit no chamador;
      `ensure_user` hoje comita internamente)
- [ ] Tirar criação da engine de import time em `database/db.py`
      (lazy/injetável, melhora testabilidade)
- [ ] Renomear `handlers/api_client.py` (nome mentiroso — é camada de dados,
      não cliente HTTP)
- [ ] Limpeza menor: typo `"Schenduled Event"` em `lambda_handler.py`;
      espanhol "apunta al" no `.env.example`
- [ ] Atualizar guidelines/docs do monorepo: seção `bot` ainda diz que o bot
      não acessa o banco diretamente — ADR 0005 reverte isso

## Fase 3 — Deploy

- [ ] Pipeline completa: testes → build dos zips → alembic no Neon →
      terraform apply → setWebhook
- [ ] Smoke pós-deploy: mensagem real no bot, wizard completo, notify horário
      disparado, logs da Lambda limpos
- [ ] Desligar containers da VM Oracle (`docker-compose.prod.yml`) — fim do
      modelo antigo

## Fase 4 — Backlog pós-deploy (fora do escopo atual)

- [ ] Remover endpoints users/alerts/matches da API do scraper
      (ADR 0005 — decisão pendente: remoção imediata vs deprecação)
- [ ] Futuro de `packages/shared-models` (ADR 0004 questão #2 / ADR 0005 #2):
      - [x] Table models SQLModel consolidados em `shared_models.tables`
            (fonte única do schema físico — ver "Decided after acceptance"
            no ADR 0005)
      - [ ] Remoção/deprecação de `api_schemas` (perde a finalidade);
            modelos de domínio e utils permanecem
- [ ] Idempotência do confirm do wizard (ADR 0006 questões #4–5)
