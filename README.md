# Imóvel Radar 🏠

Telegram bot + scraper for monitoring real-estate listings on OLX Maceió. The scraper gathers listings daily, and the bot notifies users when new properties match their registered alerts.

**Monetization:** freemium (1 free alert) + **Radar Pro via Telegram Stars** (≈ R$ 19,90/mês; Pix later) — see [`docs/adr/freemium-pix-monetization.md`](docs/adr/freemium-pix-monetization.md). Public pricing copy lives in `apps/frontend/src/content/page-content.ts`.

![Demo: `/start` and main menu](assets/imovel-radar-demo.gif)

## Stack

- **Monorepo**: Turborepo + pnpm (Node.js workspaces for the frontend)
- **Scraper** (Lambda + FastAPI local): coleta OLX → `listing` no Postgres (Neon)
- **Bot** (Lambda webhook + polling local): dona de `users`/`alerts`/`alert_matches`; lê `listing`
- **Shared package**: `shared-models` — table models SQLModel + utils; `api_schemas` está deprecated
- **Database**: Postgres via SQLModel + Alembic (dev: local; prod: Neon pooled)
- **Estado de conversa (prod)**: DynamoDB

## Structure

```text
imovel-radar/
├── packages/
│   └── shared-models/        ← tables SQLModel + domain models + utils
│       └── src/
│           ├── tables.py
│           ├── models.py
│           ├── api_schemas.py  (deprecated)
│           └── utils.py
├── apps/
│   ├── scraper/              ← dono de `listing`; coleta OLX (Lambda em prod)
│   ├── bot/                  ← webhook Lambda + Postgres direto (ADR 0005)
│   └── frontend/             ← Next.js 16 (App Router, SSG → out/)
├── docs/
│   └── adr/
│       └── separate-scraper-from-bot.md
├── assets/
├── turbo.json
├── pnpm-workspace.yaml
└── package.json
```

## Architecture / Flow

```text
  EventBridge (08:00 Maceió)    EventBridge (10:00 Maceió)
          │                              │
          ▼                              ▼
  Scraper Lambda                   Bot Lambda
  (upsert listing)                 (webhook + notify)
          │                              │
          └──────── Neon Postgres ───────┘
                         ▲
                         │
              DynamoDB (estado de conversa)
                         ▲
              Telegram ──┘ API Gateway POST /webhook
```

A bot lê `listing` e escreve `users`/`alerts`/`alert_matches` direto no banco
(ADR 0005). Não há hop HTTP scraper↔bot.

### Daily scrape flow

```text
EventBridge → scraper Lambda → job_daily()
  → search_all_rent_maceio()
  → extract_listings_from_search_page()
  → upsert listing
```

### Notification flow (EventBridge daily 2h after scrape / JobQueue in local polling)

```text
run_daily_notifications()
  → notify_new_matches()
      → SELECT users / unnotified listings por alerta
      → send_carousel() / INSERT alert_matches
  → notify_watched_changes()
      → diffs em watched_listings vs listing
      → mensagem de preço/status / update baselines
```

### `/novo_alerta` wizard flow

```text
User → preço → bairros → nome → confirma
  → INSERT alerts (idempotente)
  → carrossel de matches
```

## Bot commands

| Command | Description | Status |
|---|---|---|
| `/start` | Welcome screen and main menu | ✅ |
| `/novo_alerta` | Wizard to create a new alert | ✅ |
| `/ajuda` | Lists available commands | ✅ |

## Running

### Setup (once)

```bash
pnpm run setup
```

Then configure the `.env` files:

- `apps/scraper/.env` — copy from `apps/scraper/.env.example`
- `apps/bot/.env` — set `TELEGRAM_BOT_TOKEN` and `DATABASE_URL`

### Run everything

```bash
pnpm run dev
```

### Run a single service

```bash
pnpm run dev:scraper   # FastAPI on port 8000
pnpm run dev:bot       # Telegram Bot
pnpm run dev:frontend  # Next.js (optional)
```

## Lint and type checking

The project uses **Ruff** for linting and **Pyright** for type checking via the terminal.
VS Code Pylance is disabled; the actual validation is done through the commands below.

```bash
# Scraper
cd apps/scraper && uv run ruff check . && uv run pyright

# Bot
cd apps/bot && uv run ruff check . && uv run pyright
```

## Tests

Run the full test suite from the repository root:

```bash
pnpm run test
```

To run only the scraper tests:

```bash
pnpm run test --filter scraper
```

## CI: Scraper tests

The repository includes a GitHub Actions workflow in [.github/workflows/scraper-tests.yml](.github/workflows/scraper-tests.yml) that runs the scraper test suite automatically on pushes to `main` and on pull requests that touch [apps/scraper](apps/scraper) or the workflow file itself.

It installs dependencies with `uv`, sets up Python, and executes:

```bash
cd apps/scraper && uv run pytest -v
```

See [`docs/setup.md`](docs/setup.md) for details.
