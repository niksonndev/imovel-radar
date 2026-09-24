# Bot WhatsApp — Imóvel Radar

Cliente WhatsApp Web em Rust ([whatsapp-rust](https://github.com/oxidezap/whatsapp-rust)), sempre ligado. Cobre o mesmo fluxo do bot Telegram: alerta em linguagem natural ou passo a passo, meus alertas, carrossel de matches, watchlist e trial de Radar Pro por e-mail. Não há Telegram Stars.

Cliente não oficial: pode violar os termos da Meta e a conta pode ser suspensa.

## Como funciona

- Processo único: HTTP (`GET /health`, `GET /pair`) + sessão WhatsApp + notificação diária às 10:00 (America/Maceio), só para `users.channel = 'whatsapp'`.
- Postgres compartilhado (Neon). A migration `0012` cria `channel`, `whatsapp_jid`, a sequence de `chat_id` e `bot_session`.
- Conta WhatsApp não se vincula à conta Telegram.

## Configuração

```bash
cp apps/whatsapp-bot/.env.example apps/whatsapp-bot/.env
```

Rode a migration antes (o scraper aplica no boot, ou `cd apps/scraper && uv run alembic upgrade head`).

## Dev

```bash
cd apps/whatsapp-bot
cargo run
```

No primeiro boot o terminal imprime o QR. Também dá para abrir `http://localhost:10000/pair?token=$PAIR_SECRET`.

Compose, na raiz:

```bash
docker compose up whatsapp-bot
```

## Render

Blueprint em `render.yaml`: web service Docker, plano starter, disco de 1 GB em `/data` (a sessão SQLite não pode ser efêmera). Disco implica instância única e um curto downtime em cada deploy.

No primeiro deploy, abra `https://<serviço>/pair?token=<PAIR_SECRET>` e escaneie. Os deploys seguintes reusam `/data/whatsapp.db`.

Defina `DATABASE_URL` (Neon pooled) e `OPENAI_API_KEY` no painel. `PAIR_SECRET` é gerado pelo blueprint.

## Testes

```bash
cd apps/whatsapp-bot && cargo test
```
