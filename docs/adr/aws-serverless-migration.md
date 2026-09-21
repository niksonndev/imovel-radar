# 0004 - AWS Serverless migration (Terraform + Neon)

## Status

Accepted

> **Current topology:** production is Lambda-only (scraper + bot, API Gateway,
> EventBridge, Neon, DynamoDB). There is no Compose host in prod;
> `docker-compose.prod.yml` is retired. The Context below describes the
> historical trigger for this ADR.

## Context

Imóvel Radar previously targeted two Docker containers (`apps/scraper` and
`apps/bot`) via `docker-compose.prod.yml` / GHCR, with deployment as a manual
`docker compose ... up` step and mutable host state. Continuous integration
existed (image build + scraper tests), but **deploy was still ad-hoc**.

Several drivers pushed us to reassess that model:

- **Infra predictability.** A mutable host set up by hand is a liability. We
  want the whole infrastructure described as versioned, reviewable code
  (Terraform), so it can be recreated or moved at any time.
- **A real CI/CD pipeline.** CI that stops at "built and published" leaves
  deploy as a human-driven action with no gate, no rollback story and no
  traceability in git.
- **Zero budget is a hard constraint.** Imóvel Radar is a personal/portfolio
  project — there is no infrastructure budget. Whatever runs in prod must
  demonstrably stay at $0 (free tiers only) at the expected scale.
- **The REST API has no real consumer.** Per ADR 0001, the HTTP contract
  exists to keep the bot decoupled from the scraper's data. Today the bot is
  the only caller, so the API is machinery for a boundary we don't strictly
  need yet. Re-reading ADR 0001 under the free-tier constraint, the answer is
  that **a single shared database plus code discipline is sufficient at this
  stage**.

This ADR deliberately revisits two consequences of ADR 0001: the scraper
being the **sole owner** of the database, and the guarantee of **no publicly
exposed port** (communication only over the internal Docker network). Both
change under the serverless model.

## Decision

Replace Compose/host-based deploy with an AWS serverless architecture, with
**all infrastructure managed by Terraform**:

- **EventBridge** (scheduled rule) triggers the daily collection, replacing
  the in-process APScheduler that runs today inside the FastAPI process.
- **Scraper Lambda** runs the OLX collection plus matching/upsert on demand,
  writing to a shared Postgres database.
- **API Gateway** exposes the public HTTPS endpoint that receives Telegram's
  webhook deliveries (replacing PTB polling).
- **Bot Lambda** processes each Telegram update synchronously via PTB's
  custom-webhook pattern (`Update.de_json` → `Application.process_update`),
  with no long-running process.
- **Postgres on Neon (free tier)** is the single database shared by both
  lambdas. The current schema — four tables (`listing`, `users`, `alerts`,
  `alert_matches`) — is preserved **as is**: this migration changes the
  engine (SQLite → Postgres), not the schema design. SQLModel remains the ORM.
- **Match notification job**: the hourly "check unnotified listings per chat"
  job is re-homed as an EventBridge → bot Lambda invocation (exact shape
  pending, see "Not yet decided").
- **CI/CD pipeline** (GitHub Actions) extends the existing workflows:
  tests → build/publish Lambda artifacts → run Alembic migrations against
  Neon → `terraform plan`/`apply` (AWS credentials via OIDC — no long-lived
  keys). Where exactly the migration step runs is open (see "Not yet
  decided").
- **Local development stays as-is** (`pnpm run dev`; Docker Compose for a
  full local stack). Serverless is the production deployment model.
- **Cost target: $0 by design**, at expected volume, using only free tiers:
  Lambda (1M requests/month + 400k GB-s), API Gateway (1M requests/month),
  EventBridge/CloudWatch Events (14M events/month), S3 (5 GB), GitHub Actions
  minutes, Terraform (open source) and Neon's free tier. The traffic profile
  of a personal bot — a few users, one daily scrape, one hourly notify job —
  sits far below every cap.

## Consequences

**Positive:**

- Infra becomes **disposable and reproducible**: a fresh environment is one
  `terraform apply` away; changes go through the same review/PR flow as code.
- A real pipeline: a push to `main` (or a tag) produces a deployed, migrated
  production environment — with the migration as a blocking gate instead of a
  runtime startup step.
- HTTPS is provided by API Gateway; no reverse proxy, certificate or SSH
  maintenance.
- Zero idle cost: no host to keep paying for/rebooting; free tiers cover the
  profile.
- Serverless scaling with no capacity planning; cold-start latency is
  acceptable at this scale.
- A shared database removes HTTP contract drift — scraper and bot see the
  same rows.

**Negative / accepted trade-offs:**

- **Scraper execution model changes.** The scraper is no longer a
  continuously running process: it becomes a job-fired Lambda. OLX collections
  are capped at 130 pages with a 2–5 s delay between requests
  (`apps/scraper/config.py`), which can approach or exceed Lambda's
  **15-minute hard timeout**; the page cap or a chunking strategy needs
  revisiting (open, see below).
- **Datacenter-IP blocking risk: validated, not a blocker.** A spike using
  the same `cloudscraper` version (1.2.71) from an AWS EC2 free-tier instance
  (same AWS datacenter IP ranges Lambda would use) ran 8 consecutive requests
  against the real Maceió rent URL at the production cadence (~3 s delay
  between requests): **8/8 returned HTTP 200 with a stable response size
  (~960 KB)**, confirming 207 occurrences of `R$` — real listing content, not
  a Cloudflare challenge or block page. In scope (rental, Maceió, production
  volume/cadence). Out of the current scope, the eventual expansion to the
  sale category (~15k listings) must re-validate this assumption before it
  applies.
- **Bot communication pattern changes, not just infra.** Polling
  (`Application.run_polling`) gives way to webhook: Telegram delivers updates
  to the public API Gateway URL and expects a prompt (≤ ~29 s, API Gateway's
  integration timeout) response. PTB's `JobQueue`-based hourly job cannot run
  inside a served request, so the notification job must move out of the bot
  process entirely. (Note: today that job is effectively a no-op —
  `app.bot_data["polling_chat_ids"]` is read but never populated anywhere.)
- **Conversation state persistence.** The bot persists wizard steps and
  carousel navigation in a local file via
  `PicklePersistence(filepath=carousel_state.pickle)`. Lambda has no durable
  filesystem, so state must move to in-memory persistence (losing state on
  cold starts / concurrent invocations) or into the database — decision
  pending. The in-memory `ensure_user` cache and the module-level `httpx`
  client remain, but are now per-warm-instance.
- **SQLite → Postgres is a real engine change despite "no schema redesign".**
  `upsert_listing` uses `sqlalchemy.dialects.sqlite.insert` +
  `on_conflict_do_update` — SQLite-specific syntax that must move to the
  `postgresql` dialect. Autoincrement primary keys (`alerts.id`) map to
  `SERIAL`; SQLite PRAGMAs (`foreign_keys=ON`, WAL) disappear (Postgres enforces
  foreign keys by default); `sa.JSON`, `DateTime(timezone=True)` and
  `server_default` expressions need verification against Postgres/Neon.
- **Migrations leave the runtime.** Today Alembic runs at FastAPI startup
  (scraper lifespan). Under serverless, "migrate on boot" would race between
  concurrent instances — migrations become an explicit pipeline step whose
  failure **blocks deployment** (exact placement open, see below).
- **ADR 0001's "sole owner" boundary softens.** If the bot reads the shared
  database directly (favored direction; see "Not yet decided"), "the bot must
  not access the database" no longer holds literally. Matching business logic
  still lives in the scraper Lambda, but data access becomes shared, and code
  discipline replaces the enforced API boundary.
- **Neon free-tier specifics.** The free tier pauses compute after inactivity
  and wakes on demand (first query after a pause can be slow); serverless
  connections should use the pooled connection string. Runtime details to
  handle, not blockers.
- **Monitoring changes.** The Telegram self-alerts/heartbeat (background
  reliability net) have no long-running process to run inside; the equivalent
  becomes CloudWatch alarms on Lambda failures plus pipeline alerting.

## Alternatives considered

- **Keep Compose on a long-running host.** Still free and working as a local
  or ad-hoc option, but leaves deployment manual and infra mutable — the
  exact problems this ADR exists to solve.
- **Managed containers (ECS Fargate + ECR).** No practical free tier —
  violates the zero-cost constraint.
- **PaaS (Fly.io, Render, Railway free tiers).** Viable, but smaller free
  tiers, weaker Terraform/IaC story and more vendor lock-in than plain AWS
  primitives.
- **Keep the HTTP bot→scraper split behind API Gateway.** Preserves ADR 0001
  as-is, but at the cost of operating an API layer with no external consumer.
  Revisit when a dashboard/public API actually exists — the shared-DB model
  does not preclude re-adding an API later.
- **Self-hosted Postgres on a long-running host instead of Neon.** Removes
  managed-DB convenience and keeps a host in the critical path; Neon's free
  tier removes both.

## Not yet decided

1. **Scheduler orchestration.** EventBridge dispara a coleta; chunking/retry
   interno da scraper Lambda para caber nos 15 minutos ainda pode evoluir.

## Decided after acceptance

- **`packages/shared-models`:** table models em `shared_models.tables`;
  `api_schemas` deprecated após remoção da API users/alerts/matches.
- **Secrets:** SSM Parameter Store (`telegram_bot_token` bootstrap fora do TF;
  `database_url` no TF). Webhook `secret_token` gerado no Terraform e injetado
  na Lambda / `setWebhook`.
- **Migrations:** `alembic upgrade head` no CI **antes** de `terraform apply`.
- **Bot conversation state:** DynamoDB via `BasePersistence` (ADR 0006).
- **Bot DB access:** bot dona de users/alerts/matches (ADR 0005).
