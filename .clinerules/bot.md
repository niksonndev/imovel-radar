---
paths:
  - "apps/bot/**"
---

# Bot — Imóvel Radar (Python)

Telegram bot that monitors real estate listings and notifies users via configurable alerts.

## Stack

- Python, python-telegram-bot (PTB) — JobQueue for local polling; EventBridge in production.
- Direct Postgres access (ADR 0005) via `handlers/data.py` + `database/queries.py`.
- DynamoDB `BasePersistence` in production (ADR 0006).

## Architecture (layers)

- bot → Neon Postgres (`users` / `alerts` / `alert_matches` writes; `listing` reads)
- scraper writes `listing` only
- `handlers/`, `jobs/`, `models.py` stay separated
- `models.py` centralizes TypedDicts (`CreateAlertDraft`, `CreateAlertWizardState`, `UserData`)
- `CustomContext` is the standard handler context

## What to avoid

- Do not reintroduce APScheduler.
- Do not reintroduce an HTTP client to the scraper for users/alerts/matches.
- ConversationHandler multi-step flows must be `persistent=True` with a `name`.

## Library documentation

Before writing or modifying code that uses any of the libraries below, consult the `get_docs` tool from the `context` MCP — do not rely on training memory for their APIs:

- `python-telegram-bot`

This applies to every code change involving these libraries — including small fixes, 
type errors, and lint corrections, not just new code. If you are about to fix a typing 
or lint error in a file using one of these libraries, call get_docs first.
