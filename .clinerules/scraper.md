---
paths:
  - "apps/scraper/**"
---
# Scraper — Imóvel Radar (Python)

Lambda (prod) / FastAPI health (dev) responsible for OLX scraping and `listing` persistence.

## Stack

- Python; FastAPI only for local `/health` + Alembic on startup
- Daily collection: EventBridge → Lambda (`lambda_handler.py`)
- cloudscraper + BeautifulSoup + lxml
- Postgres (SQLModel + Alembic) — writer of `listing` only (ADR 0005)

## Architecture (layers)

- scheduler → collector → parser → Postgres (`listing`)
- The bot owns `users`, `alerts`, `alert_matches` and reads `listing` directly
- Do not re-add REST endpoints for users/alerts/matches

## What to avoid

- Do not write `users` / `alerts` / `alert_matches` from the scraper
- Do not restore the old bot HTTP API

## Library documentation

Before writing or modifying code that uses any of the libraries below, consult the `get_docs` tool from the `context` MCP — do not rely on training memory for their APIs:

- `sqlmodel`
- `alembic`

This applies to every code change involving these libraries — including small fixes, 
type errors, and lint corrections, not just new code. If you are about to fix a typing 
or lint error in a file using one of these libraries, call get_docs first.
