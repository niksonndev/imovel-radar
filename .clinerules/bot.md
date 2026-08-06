---
paths:
  - "apps/bot/**"
---

# Bot — Imóvel Radar (Python)

Telegram bot that monitors real estate listings and notifies users via configurable alerts.

## Stack

- Python, python-telegram-bot (PTB) — uses PTB's native `JobQueue` for scheduling (do not use APScheduler).
- httpx — HTTP client for the scraper API.
- Does not access the database — all business logic lives in the Scraper service.

## Architecture (layers)

- bot → (HTTP via ScraperAPI) → scraper API
- `handlers/`, `jobs/`, `models.py` — do not recreate a generic `bot/` folder mixing these responsibilities; the separation was done deliberately.
- `models.py` centralizes the project's TypedDicts (`CreateAlertDraft`, `CreateAlertWizardState`, `UserData`). New types shared across modules go here, not scattered around.
- `CustomContext` (via PTB's `CallbackContext`) is the standard context type for handlers — do not use the generic `CallbackContext` directly in a new handler.

## What to avoid

- Do not reintroduce APScheduler — the project deliberately migrated to PTB's native `JobQueue`.
- Do not access the database directly — all communication with the scraper goes through the REST API (`ScraperAPI`).

## Library documentation

Before writing or modifying code that uses any of the libraries below, consult the `get_docs` tool from the `context` MCP — do not rely on training memory for their APIs:

- `python-telegram-bot`

This applies to every code change involving these libraries — including small fixes, 
type errors, and lint corrections, not just new code. If you are about to fix a typing 
or lint error in a file using one of these libraries, call get_docs first.