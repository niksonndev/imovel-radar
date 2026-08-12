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

Add a centralized user guard at the PTB application level, **before** any
handler runs, by subclassing the `Application` and overriding
`Application.process_update`:

- `RadarApplication(Application)` overrides `Application.process_update` to
  call `ensure_user(chat_id)` for the `effective_user` of every
  `telegram.Update` (messages, commands, callbacks and conversation steps),
  then delegates to `super().process_update(...)`.
- `ensure_user(chat_id)` performs:
  - `GET /users/{chat_id}` to check existence
  - `POST /users/{chat_id}` to create if missing
- `ensure_user` keeps an in-memory cache (`set[int]`) of already-provisioned
  `chat_id`s, so after the first successful interaction the bot does not hit
  the Scraper API again for that user.
- Because the guard runs in `process_update` — not as a handler — it never
  "consumes" the update, so PTB continues dispatching to specific handlers
  normally (PTB stops a group after the first matching handler, so a generic
  global `MessageHandler` would block the others).
- If the Scraper API is unavailable, `ensure_user` logs the exception and
  returns (**fail-open**). The friendly error message, when desired, is left to
  the handler that actually uses the user.

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
- The guard runs in `Application.process_update` — no extra handler entries are
  added to the PTB dispatch queue, so there is no per-update handler overhead.
  The only cost is the (cached) HTTP call on each user's first interaction.
