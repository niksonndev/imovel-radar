# 0002 - User identity is the Telegram chat_id

## Status

Accepted

## Context

The original schema had two identifiers for a user:

- `users.id`: an internal auto-increment primary key
- `users.chat_id`: the Telegram chat id, marked `UNIQUE`

`alerts.user_id` was a foreign key pointing to `users.id`.

This created a duplicated identity: an arbitrary internal id plus the Telegram
`chat_id`. Because the bot needs the `chat_id` to send notifications, the code
required two extra pieces to bridge the gap:

- `AlertWithChat`, a model that JOINed `alerts` with `users` to carry the
  `chat_id` alongside each alert.
- `ensure_user`, a function that translated a `chat_id` into the internal
  `users.id` on every API call that involved a user.

Identity is already delegated to Telegram (see ADR 0001) — there is no custom
authentication system. The internal `users.id` was therefore unnecessary
indirection: the `chat_id` alone is the stable, meaningful user identifier.

## Decision

The Telegram `chat_id` becomes the primary key of the `users` table
(`chat_id INTEGER PRIMARY KEY`), and `alerts.user_id` stores the `chat_id`
directly (foreign key to `users(chat_id)`).

The following were removed/simplified:

- The `users.id` column.
- The `AlertWithChat` Pydantic model.
- The `ensure_user` translation logic — it becomes a plain
  `INSERT OR IGNORE INTO users (chat_id) VALUES (?)`.
- The JOIN in the active-alerts query, renamed from
  `list_active_alerts_with_chat` to `list_active_alerts`.
- The polling endpoint was renamed from `GET /alerts/active/with-chat` to
  `GET /alerts/active`.

The bot now uses `alert.user_id` (which is the `chat_id`) directly when sending
notifications.

## Consequences

**Positive:**

- Eliminates the duplication between internal id and `chat_id`, and the
  `ensure_user`/`AlertWithChat` bridging code.
- `Alert` alone now carries everything the bot needs (`user_id` is the
  `chat_id`), so no extra model or JOIN is required for notifications.
- Less code to maintain on both the scraper and the bot sides.

**Negative / accepted trade-offs:**

- Schema change. No migration path is provided — the project is still in
  development with no critical data, so the database can be recreated from the
  new schema.