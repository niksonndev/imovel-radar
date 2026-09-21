# Scraper — Imóvel Radar

Coleta diária de anúncios OLX (Maceió / aluguel) e persistência em `listing`.

- **Prod:** AWS Lambda + EventBridge (`lambda_handler.py`). Sem FastAPI.
- **Dev:** FastAPI só para `/health` e para aplicar Alembic no startup.
- Dono exclusivo de `listing`. Users/alerts/matches são da bot (ADR 0005).

## Endpoints (dev local)

| Method | Route | Description |
|--------|-------|-------------|
| GET | `/health` | Health check e conectividade com o banco |

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
uv sync
uv run uvicorn main:app --reload --port 8000
```

## Lambda / EventBridge

The daily collection runs as an AWS Lambda triggered by EventBridge
(`lambda_handler.py`). The handler never runs migrations (Alembic is a
pipeline step) and does not import the FastAPI app.

```bash
cd apps/scraper
uv run python -m scheduler.jobs
```

## CI / tests

```bash
pnpm run test --filter scraper
```

## Architecture

```text
apps/scraper/
├── main.py              # FastAPI local (health + migrations)
├── config.py
├── database/            # queries de listing
├── lambda_handler.py    # EventBridge → job_daily
├── collector/
├── api/health.py
├── scheduler/
└── alembic/
```
