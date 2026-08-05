---
paths:
  - "apps/scraper/**"
---
# Scraper — Imóvel Radar (Python)

FastAPI service responsible for all business logic: OLX scraping, SQLite persistence, and the REST API for the bot.

## Stack

- Python, FastAPI, uvicorn
- APScheduler (internal scheduler — daily collection job)
- cloudscraper + BeautifulSoup + lxml (Cloudflare bypass + RSC extraction)
- SQLite (native sqlite3) — sole owner of the database

## Architecture (layers)

- scheduler → collector → parser → SQLite → REST API
- The scraper is the **sole owner of the SQLite database** — the bot does not access the database directly.
- Exposes a REST API (FastAPI) for the bot to consume listings, alerts, and matches.

## What to avoid

- Do not move business logic into the bot — the scraper owns the database and the business rules.
- Do not let the bot access the database directly — all communication goes through the REST API.

## Library documentation

Before writing or modifying code that uses any of the libraries below, consult the `get_docs` tool from the `context` MCP — do not rely on training memory for their APIs:

- `sqlmodel`
- `alembic`