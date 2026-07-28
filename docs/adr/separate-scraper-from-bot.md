# 0001 - Separate Scraper from Bot

## Status

Accepted

## Context

Imóvel Radar started as a single Python process: the Telegram bot contained, in the same codebase, OLX scraping logic, database access (SQLite), and orchestration of the conversation with the user.

This coupling has already caused concrete problems:

- A silent scraper failure (a change in OLX's HTML structure, causing it to stop returning new listings) was only noticed by the absence of results, with no alert at all. This motivated adding Telegram self-alerts and a heartbeat, but didn't address the root cause: scraper and bot living in the same process makes it hard to isolate failures on one side without affecting the other.
- There was no clear boundary between "who reads/writes to the database" and "who talks to the user," which tends to generate business logic duplication on both sides as the project grows (e.g., alerts, matches, multiple cities).
- Testing the whole bot (scraping + database + conversation) runs into the testing tool limitations of the python-telegram-bot library (PTB), making it hard to test the part that most needs coverage: scraping and matching logic.

The project is migrating to a monorepo orchestrated by Turborepo, which makes it natural to revisit this division now, before rebuilding the bot.

## Decision

Split the project into two services with well-defined responsibilities:

- **Scraper**: sole owner of the database (SQLite). It's a FastAPI service that runs its own internal scraping scheduler in the background, in the same process/container (avoiding write-lock contention on SQLite). It exposes an HTTP API for:
  - Querying new listings (polling, e.g. `GET /listings?since=<timestamp>`)
  - Creating and managing alerts (`POST /alerts`, `DELETE /alerts/{id}`)
  - Computing the match between a new listing and registered alerts — this logic lives in the scraper, not the bot, since it owns the data and the criteria.

- **Bot**: a "dumb" client of the scraper's API. It doesn't access the database directly and doesn't implement business logic (matching, persistence). It only:
  - Translates the Telegram conversation into HTTP calls to the scraper (e.g. `POST /alerts` with the user's criteria)
  - Polls for results/matches and sends them as Telegram messages

Both services run as separate Docker containers on the same Oracle VM, communicating over the internal Docker Compose network (no publicly exposed port, no reverse proxy at this stage). The contract between them is typed via Pydantic schemas shared in a common package in the monorepo.

The Telegram `chat_id` is used as the user identifier in API calls — there's no custom authentication system; identity is delegated to Telegram.

## Consequences

**Positive:**

- A scraper failure doesn't bring down the bot (and vice versa); each service can be restarted/deployed independently.
- Eliminates business logic duplication: all matching logic and data access lives in a single place.
- Improves testability: the logic that matters most to test (scraping, parsing, matching, API endpoints) lives in FastAPI, testable with `TestClient` and pure functions, without depending on PTB's limited tooling. The bot, having no business logic of its own, needs far less test coverage — what remains is isolated in pure functions outside the handlers (message formatting, user input parsing, mockable HTTP client).
- Opens a natural path toward a future public API (e.g. for a dashboard), without needing to touch the already-established separation of responsibilities.

**Negative / accepted trade-offs:**

- One more service to operate (two containers instead of a single process), even though on the same VM.
- Introduces network latency (even if local, via Docker) between bot and scraper, where before it was a direct function call.
- Requires keeping an API contract (Pydantic schemas) in sync between both sides — mitigated by a shared package in the monorepo.

## Alternatives considered

- **Keep everything in a single process**: simpler in the short term, but perpetuates the coupling that already caused the silent failure mentioned in the context, and doesn't solve the bot's testability problem.
- **Separate into different VMs right away**: unnecessary at this stage — Oracle Free Tier allows up to 4 VMs via the Ampere A1 instance, so there's room for this in the future, but separating into containers on the same VM already delivers sufficient process and failure isolation for now.
- **Expose communication via a reverse proxy with public HTTPS**: deferred until there's an actual external consumer (e.g. a dashboard), since today only the bot consumes the API, within the same Docker network.