---
paths:
  - "apps/scraper/**"
---
# Scraper — Imóvel Radar (Python)

FastAPI service responsible for all business logic: OLX scraping, Postgres persistence, and the REST API for the bot.

## Stack

- Python, FastAPI, uvicorn
- APScheduler (internal scheduler — daily collection job)
- cloudscraper + BeautifulSoup + lxml (Cloudflare bypass + RSC extraction)
- Postgres (via SQLModel + Alembic) — sole owner of the database

## Architecture (layers)

- scheduler → collector → parser → Postgres → REST API
- The scraper is the **sole owner of the Postgres database** — the bot does not access the database directly.
- Exposes a REST API (FastAPI) for the bot to consume listings, alerts, and matches.

## What to avoid

- Do not move business logic into the bot — the scraper owns the database and the business rules.
- Do not let the bot access the database directly — all communication goes through the REST API.

## Library documentation

Before writing or modifying code that uses any of the libraries below, consult the `get_docs` tool from the `context` MCP — do not rely on training memory for their APIs:

- `sqlmodel`
- `alembic`

This applies to every code change involving these libraries — including small fixes, 
type errors, and lint corrections, not just new code. If you are about to fix a typing 
or lint error in a file using one of these libraries, call get_docs first.