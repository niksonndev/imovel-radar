# Scraper — Imóvel Radar

FastAPI service responsible for the core business logic of Imóvel Radar:

- Owns the Postgres database (SQLModel + Alembic, via `DATABASE_URL`)
- Runs daily OLX scraping for rental listings in Maceió
- Exposes a REST API for listings, alerts, users, and match tracking
- Daily collection is triggered by EventBridge (AWS Lambda) — see `lambda_handler.py`

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
DATABASE_URL=postgresql+psycopg://postgres:teste123@localhost:5432/imovel_radar
MACEIO_RENT_LISTINGS_URL=https://www.olx.com.br/imoveis/aluguel/estado-al/alagoas/maceio
```

## How to run

```bash
cd apps/scraper
uv pip install -e ../../packages/shared-models
uv sync
uv run uvicorn main:app --reload --port 8000
```

## Lambda / EventBridge

The daily collection runs as an AWS Lambda triggered by EventBridge
(`lambda_handler.py`). The handler never runs migrations (Alembic is a
pipeline step) and does not import the FastAPI app.

Run the collection manually (same code path as the Lambda):

```bash
cd apps/scraper
uv run python -m scheduler.jobs
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
├── main.py              # FastAPI app + lifespan (applies migrations; dev only)
├── config.py            # Environment variables (OLX, scraping, delay, app settings)
├── database/            # Postgres schema, queries, DB access, users
├── lambda_handler.py    # AWS Lambda entry point (EventBridge trigger)
├── collector/           # OLX scraper + parser (RSC payload extraction)
├── api/                 # FastAPI routes (health, users, listings, alerts)
├── scheduler/           # job_daily (collection) — Lambda/manual
├── alembic/             # Database migrations
└── docs/                # Project documentation
```