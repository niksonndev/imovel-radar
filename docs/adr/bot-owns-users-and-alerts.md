# 0005 - The bot owns users/alerts and reads the database directly

## Status

Accepted

## Context

ADR 0001 established the bot as a "dumb client": the scraper is the **sole
owner** of the database and the bot only talks to it through the HTTP REST
API. ADR 0004 (AWS serverless) already flagged that this boundary softens
under serverless: the bot stops being a long-running process on the same
Docker network as the scraper, and the REST API is machinery for a boundary
with no external consumer. ADR 0004 left as an open question (#7) whether the
bot would access the shared Postgres directly.

Three concrete facts drive this decision:

- `users` and `alerts` are born from user interaction with the bot: user
  provisioning (`ensure_user`, ADR 0003) and the `/novo_alerta` wizard. They
  describe the user, not the scraping pipeline.
- The notification flow needs to read unnotified listings
  (`get_unnotified_listings_for_user`) and record matches (`alert_matches`) —
  both currently reached through HTTP calls to the scraper.
- With webhook + Lambda, that HTTP hop would have to cross API Gateway
  (public) or disappear in favor of the shared database.

## Decision

The bot becomes the **direct owner** of the `users`, `alerts` and
`alert_matches` tables in the shared Postgres (Neon), and **reads** `listing`
directly (read-only) to compute unnotified listings for notifications.

The scraper keeps the write side of `listing` (scraping, parsing, upsert) and
the scheduler. The ownership matrix is explicit — **one writer per table**:

| Table          | Writer  | Reader            |
|----------------|---------|-------------------|
| `listing`      | scraper | scraper, bot      |
| `users`        | bot     | bot, scraper      |
| `alerts`       | bot     | bot, scraper      |
| `alert_matches`| bot     | bot               |

Consequences of this decision, deliberately:

- **Reverses the ADR 0001 boundary** ("scraper is the sole owner; the bot
  does not access the database") and **resolves open question #7 of ADR
  0004**.
- `ensure_user` (ADR 0003) becomes a direct, idempotent DB upsert
  (`INSERT ... ON CONFLICT DO NOTHING`) instead of HTTP GET/POST; the
  in-memory per-process cache stays.
- The scraper's REST endpoints for users/alerts/matches are deprecated and
  removed; the HTTP contract for that path (`shared_models.api_schemas`)
  loses its purpose (the future of `packages/shared-models` is re-opened, see
  "Not yet decided").

## Consequences

**Positive:**

- Removes the HTTP hop and contract drift on the user/alerts/notification
  path — scraper and bot see the same rows with no serialization boundary.
- The API layer that had no real consumer disappears from this path.
- Notifications become direct DB reads/writes; the pipeline is simpler.
- A future dashboard/public API can re-expose a deliberate API instead of
  inheriting an accidental one (already anticipated by ADR 0004).

**Negative / accepted trade-offs:**

- Reverses ADR 0001: the bot is no longer a "dumb client". It becomes a data
  owner, which moves more logic and test surface into the bot.
- The matching queries (`get_unnotified_listings_for_user` and friends) must
  move or be shared (open, see below).
- Discipline is required to avoid dual writers: the ownership matrix above is
  the contract.
- The scraper loses the ability to "own" user-facing data it used to serve;
  any shared read paths must be intentional.
- `shared_models.api_schemas` becomes dead weight on this path.

## Alternatives considered

- **Keep the HTTP bot→scraper split** (API Gateway in front of the scraper):
  preserves ADR 0001 verbatim, but sustains an API layer with no consumer and
  forces the bot's data path through a public endpoint.
- **Read-only bot, keep writes in the scraper API**: a hybrid that keeps two
  access patterns for the same tables and the API alive for half the work —
  more complexity than either pure option.

## Not yet decided

1. Where the matching queries live (duplicated in the bot vs. moved to a
   shared location such as `packages/shared-models`).
2. Future of `packages/shared-models`: `api_schemas` loses purpose on this
   path, while domain models and utils remain useful (re-opens question #3 of
   ADR 0004).
3. Deprecation/removal path of the scraper's user/alerts/matches endpoints
   (immediate removal vs. staged deprecation during switchover).
4. Idempotency implementation for alert creation (see ADR 0006, confirm
   flow).
