# 0003 - Auto-provision user on first contact

## Status

Accepted

## Context

The Telegram bot now interacts with the Scraper API using `chat_id` as the
user identifier (see ADR 0002). Before this change, the bot had no guarantee
that a `chat_id` existed in the Scraper's `users` table before performing
operations such as creating alerts or polling listings.

If a user started the bot or triggered any handler before their Telegram
`chat_id` was created in the Scraper, API calls would fail with 404s and the
user would see error messages.

We needed a mechanism to ensure a user exists in the Scraper before any
business logic runs, without polluting every existing handler with repetitive
user-creation code.

## Decision

Add a generic user guard at the PTB application level:

- Register two handlers **before** all specific handlers in `Application`:
  - `CallbackQueryHandler(ensure_user_callback, pattern=r".*")`
  - `MessageHandler(filters.ALL, ensure_user_message)`
- These handlers call `ensure_user(chat_id)`, which performs:
  - `GET /users/{chat_id}` to check existence
  - `POST /users/{chat_id}` to create if missing
- `ensure_user` keeps an in-memory cache (`set[int]`) of already-provisioned
  `chat_id`s, so after the first successful interaction the bot does not hit
  the Scraper API again for that user.
- The handlers return `None` (do not consume the update), so PTB continues
  dispatching to specific handlers normally.
- If the Scraper API is unavailable, `ensure_user` logs the exception and
  returns (**fail-open**), allowing the user flow to continue.

## Consequences

**Positive:**

- No need to touch existing handlers (`start`, `help`, `meus_alertas`,
  `create_new_alert`, etc.). The guard is centralized.
- After the first successful interaction, zero overhead per message (in-memory
  cache).
- Fails open: Scraper downtime does not block the user from interacting with
  the bot; only the backend-dependent features break.
- Guarantees `chat_id` exists before any API call, preventing 404 cascades.

**Negative / accepted trade-offs:**

- Cache is in-memory only; after a bot restart each user is re-verified once.
  This is acceptable because it is a single cheap API call per user.
- The generic callbacks add two handler entries to the PTB dispatch queue on
  every update. The overhead is negligible compared to the HTTP calls already
  performed.
