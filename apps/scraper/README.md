# Scraper — Imóvel Radar

FastAPI service responsible for the core business logic of Imóvel Radar:

- Exclusive owner of the SQLite database (`data/imoveis.db`)
- Runs daily OLX scraping for rental listings in Maceió
- Exposes a REST API for listings, alerts, users, and match tracking
- Uses an internal APScheduler job to run the scraping cycle in the same process

## Endpoints

### Health

| Method | Route | Description |
|--------|-------|-------------|
| GET | `/health` | Service health check and database connectivity validation |

### Users

| Method | Route | Description |
|--------|-------|-------------|
| POST | `/users/{chat_id}` | Creates a user based on the Telegram `chat_id` |
| GET | `/users/{chat_id}` | Returns the user for the given `chat_id` |

### Listings

| Method | Route | Description |
|--------|-------|-------------|
| GET | `/listings/{chat_id}/unnotified` | Returns unnotified listings for all active alerts of a user |
| POST | `/listings/{chat_id}/mark-notified` | Marks a list of `(alert_id, listing_id)` pairs as notified |
| GET | `/listings/neighbourhoods` | Returns available neighbourhoods for the configured municipality |

### Alerts

| Method | Route | Description |
|--------|-------|-------------|
| POST | `/alerts` | Creates a new alert (`CreateAlertRequest`) |
| GET | `/alerts/{chat_id}` | Lists all alerts for a user |
| GET | `/alerts/{chat_id}/active` | Lists only active alerts for a user |
| GET | `/alerts/{chat_id}/{alert_id}` | Returns a specific alert for a user |
| DELETE | `/alerts/{chat_id}/{alert_id}` | Deletes a specific alert for a user |

## Configuration

Environment variables (`.env`):

```bash
LOG_LEVEL=INFO
API_PORT=8000
SCRAPE_CRON_HOUR=8
SCRAPE_CRON_MINUTE=0
SCRAPE_TIMEZONE=America/Maceio
MACEIO_RENT_LISTINGS_URL=https://www.olx.com.br/imoveis/aluguel/estado-al/alagoas/maceio
```

## How to run

```bash
cd apps/scraper
uv pip install -e ../../packages/shared-models
uv sync
uv run uvicorn main:app --reload --port 8000
```

## CI / tests

This project includes a GitHub Actions workflow at [.github/workflows/scraper-tests.yml](../../.github/workflows/scraper-tests.yml) that runs the scraper test suite on pushes to `main` and on pull requests affecting the scraper code.

The workflow installs dependencies with `uv` and runs:

```bash
pnpm run test --filter scraper
```

To run the tests locally:

```bash
pnpm run test --filter scraper
```

## Architecture

```text
apps/scraper/
├── main.py              # FastAPI app + lifespan (applies migrations, starts scheduler)
├── config.py            # Environment variables (OLX, scraping, delay, app settings)
├── database/            # SQLite schema, queries, DB access, users
├── collector/           # OLX scraper + parser (RSC payload extraction)
├── api/                 # FastAPI routes (health, users, listings, alerts)
├── scheduler/           # APScheduler jobs for regular scraping and updates
├── alembic/             # Database migrations
├── data/                # SQLite database directory
└── docs/                # Project documentation
```