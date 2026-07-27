---
paths:
  - "apps/backend/**"
---

# Backend — Imóvel Radar (Python)

Telegram bot that monitors real estate listings via OLX scraping and notifies users through configurable alerts.

## Stack

- Python, python-telegram-bot (PTB) — uses PTB's native `JobQueue` for scheduling (do not use APScheduler, it was deliberately migrated away from).
- SQLite as the database.
- OLX scraper — note: the site migrated from Pages Router to App Router (RSC). Any scraper change must account for this structure when extracting page data, not the old one.

## Architecture (layers)

```
scheduler → scraper → parser → SQLite → bot
```

- `handlers/`, `jobs/`, `context.py` — do not recreate a generic `bot/` folder mixing these responsibilities; the separation was done deliberately (dissolved out of `/bot` into the top level).
- `types.py` centralizes the project's TypedDicts (`CreateAlertDraft`, `CreateAlertData`, `BotUserData`). New types shared across modules go here, not scattered around.
- `CustomContext` (via PTB's `CallbackContext`) is the standard context type for handlers — do not use the generic `CallbackContext` directly in a new handler.
- Scraping failure alerts are sent to the admin via Telegram — when adding new critical failure points in the scraper, consider whether they deserve the same alert.

## Database

- `GET_FILTERED_LISTINGS_SQL` uses `LEFT JOIN ... IS NULL` to exclude already-notified listings — this is the standard pattern for similar "not yet processed" queries; prefer it over `NOT IN (subquery)`.
- SQLite uses named placeholders (`:name`) in queries — stay consistent, don't mix with positional `?` in the same file.

## Known tech debt

- The scraper's pagination loop can't distinguish a legitimate end-of-results from a mid-crawl block. If working in this area, keep this in mind — it's not a bug to "fix in passing," it's an unresolved structural limitation.

## What to avoid

- Do not reintroduce APScheduler — the project deliberately migrated to PTB's native JobQueue.
- Do not assume the presence of a frontend or an exposed HTTP API — today the backend only talks to Telegram and the local SQLite.

## Library documentation

Before writing or modifying code that uses SQLModel, consult the `get_docs` tool from the `context` MCP for the `sqlmodel` library — do not rely on training memory for the ORM's API.