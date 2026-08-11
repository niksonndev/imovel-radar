# Imóvel Radar 🏠

Telegram bot + scraper for monitoring real-estate listings on OLX Maceió. The scraper gathers listings daily, and the bot notifies users when new properties match their registered alerts.

![Demo: `/start`, main menu, and beginning of the New Alert flow](assets/demo-aluguel.gif)

## Stack

- **Monorepo**: Turborepo + pnpm (Node.js workspaces for the frontend)
- **Scraper** (FastAPI, port 8000): `cloudscraper` + `BeautifulSoup4` + `APScheduler`
- **Bot** (python-telegram-bot, port 3333): `httpx` (HTTP client to the scraper)
- **Shared package**: `shared-models` — Pydantic schemas defining the contract between services
- **Database**: SQLite via native `sqlite3` (exclusive to the scraper)

## Structure

```text
imovel-radar/
├── packages/
│   └── shared-models/        ← Pydantic schemas for the contract (Listing, Alert, etc.)
│       └── src/
│           ├── models.py
│           ├── api_schemas.py
│           └── utils.py
├── apps/
│   ├── scraper/              ← FastAPI — owns SQLite, scrapes OLX, exposes REST API
│   │   ├── main.py           (FastAPI + lifespan → APScheduler)
│   │   ├── config.py         (OLX URLs, delays, user agents)
│   │   ├── database/         (schema, queries, DB access, users)
│   │   ├── collector/        (OLX scraper and parser)
│   │   ├── api/              (health, users, listings, alerts)
│   │   ├── scheduler/        (APScheduler — daily scraping)
│   │   ├── data/             (imoveis.db)
│   │   ├── docs/
│   │   │   ├── README.md
│   │   │   ├── olx-scraper.md
│   │   │   └── parser.md
│   │   └── README.md
│   ├── bot/                  ← PTB — lightweight client of the scraper API
│   │   ├── main.py           (PTB Application + polling setup)
│   │   ├── config.py         (TELEGRAM_BOT_TOKEN, SCRAPER_API_URL)
│   │   ├── models.py         (CustomContext, UserData, wizard types)
│   │   ├── handlers/         (conversation flow, UI, API client)
│   │   │   ├── api_client.py (httpx → scraper)
│   │   │   ├── carousel.py
│   │   │   ├── create_new_alert.py
│   │   │   ├── meus_alertas.py
│   │   │   ├── hydrator.py
│   │   │   ├── setup.py
│   │   │   └── ui/           (keyboards, menus)
│   │   ├── jobs/             (polling_job — checks matches every hour)
│   │   └── README.md
│   └── frontend/             ← Next.js (unchanged)
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
                   ┌───────────────────┐
                   │  Scraper (8000)   │
                   │  FastAPI          │
                   │                   │
  ┌─────────┐  cron │  ┌─────────────┐  │
  │ APSched.│──────▶│  │ scrape OLX  │  │
  │ daily   │       │  │ → upsert DB │  │
  └─────────┘       │  └─────────────┘  │
                   │                   │
                   │  ┌─────────────┐  │
                   │  │ REST API    │  │
                   │  │ /users      │  │
                   │  │ /listings   │  │
                   │  │ /alerts     │  │
                   │  └─────────────┘  │
                   └────────┬──────────┘
                            │ HTTP (localhost)
                   ┌────────▼──────────┐
                   │  Bot (3333)       │
                   │  python-telegram- │
                   │  bot + httpx      │
                   │                   │
  ┌─────────┐       │  ┌─────────────┐  │
  │ Polling │       │  │ Handlers    │  │
  │ 1 hour  │──────▶│  │ → Telegram  │  │
  └─────────┘       │  └─────────────┘  │
                   └───────────────────┘
```

### Daily scrape flow

```text
APScheduler → job_daily()
  → search_all_rent_maceio()          # cloudscraper: all OLX pages
  → extract_listings_from_search_page()  # parser: discards empty entries
  → upsert listings in the database     # INSERT OR REPLACE in listings
```

### Notification flow (bot polling every hour)

```text
PTB JobQueue → notify_new_matches()
  → GET /alerts/{chat_id}/active          # all active alerts
  → for each alert:
      GET /alerts/{chat_id}/{alert_id}    # alert details
      GET /listings/{chat_id}/unnotified  # unnotified listings
      send_carousel()                     # sends a carousel to the user
      POST /listings/{chat_id}/mark-notified  # marks as notified
```

### `/novo_alerta` wizard flow

```text
User → chooses price → selects neighbourhoods → names alert → confirms
  → POST /alerts                       # creates the alert in the scraper
  → GET /alerts/{chat_id}              # reads the user's alerts
  → send_carousel()                    # sends result cards
  → POST /listings/{chat_id}/mark-notified  # marks matches as notified
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
- `apps/bot/.env` — set `TELEGRAM_BOT_TOKEN` and `SCRAPER_API_URL=http://localhost:8000`

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
