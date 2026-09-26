# 0006 - Bot conversation state persisted in DynamoDB (PTB BasePersistence)

## Status

Accepted

## Context

With webhook + Lambda (ADR 0004), the bot has no continuous process, so state
that lives in a long-running process disappears. Today the bot persists
conversation state in a local file via
`PicklePersistence(carousel_state.pickle)`: `user_data` (the wizard draft and
the wizard UI state), `chat_data` (carousel navigation) and
`conversation_data` (the `ConversationHandler` current-state pointer).

The `/novo_alerta` flow is a multi-step `ConversationHandler`
(`PRICE → NEIGHBOURHOODS → NAME → CONFIRM`); every step depends on the
previous one. The carousel, sent after an alert is created or when matches
are found, stores its listings in `chat_data` so "next/prev" navigation can
render without re-fetching.

Two facts make the store choice tractable:

- The handlers already guard against missing state ("Sessão expirada. Use
  /novo_alerta novamente.") — an expired draft is a first-class path, not an
error.
- Lambda invocations can run **in parallel and out of order** (e.g. rapid
  button taps produce multiple webhook deliveries), so the state store must
  handle concurrent read-modify-write for the same `chat_id`.

## Decision

Persist PTB conversation state in **DynamoDB** via a **custom `BasePersistence`**
implementation, passed to `Application.builder().persistence(...)`. The
`ConversationHandler` and the handlers themselves remain unchanged.

The persistence backend stores `user_data`, `chat_data` (carousel included)
and `conversation_data`, keyed by `chat_id`.

- **Native DynamoDB TTL** expires abandoned drafts automatically — no cleanup
  job; the existing "session expired" handlers are the UX.
- **Optimistic concurrency**: each write carries a `version`/`updated_at`
  attribute and uses a `ConditionExpression` on `put_item`; on conflict the
  invocation re-reads and retries. This is what makes the store correct under
  parallel/out-of-order webhook deliveries (e.g. double-tap on buttons).
- **Postgres/Neon remains the final destination**: only on confirm is the
  alert created (see ADR 0005 — the bot owns `alerts`). The confirm write is
  **idempotent** (an idempotency key derived from the draft), so a retried or
  double-tap confirm cannot create duplicate alerts.
- The **carousel is included** via `chat_data` (one Dynamo item per chat), so
  navigation survives cold starts without sharing a global 400 KB blob.
- This **resolves open question #6 of ADR 0004** (bot conversation state).

## Alternatives considered

- **In-memory / `DictPersistence`**: state resets on cold start and is wrong
  under parallel invocations (no shared store). This is the "do nothing"
  baseline.
- **`PicklePersistence` backed by S3**: its read-modify-write is not atomic —
  parallel invocations would corrupt state.
- **Redis / ElastiCache**: cost and operational overhead out of scope for the
  free-tier budget.
- **Postgres table (`alert_drafts`)**: mixes ephemeral conversation state
  with permanent domain data and requires manual or scheduled cleanup. The
  deciding factor is separation of concerns plus native TTL — not IOPS (the
  load at this scale would not stress either store).
- **`callback_data` embedding**: only covers button-choice steps, breaks at
  the free-text name step, and forces a hybrid flow; the 64-byte per-callback
  ceiling is a real limit as alert filters grow.

## Consequences

**Positive:**

- Clean separation between ephemeral (conversation) and permanent (domain)
  data.
- Native TTL — no cleanup job to operate.
- Correct under serverless concurrency thanks to conditional writes.
- DynamoDB free tier (25 GB storage, 25 RCU/WCU) is permanent, not a trial.
- `ConversationHandler` and handlers stay unchanged — only the persistence
  plug-in changes.

**Negative / accepted trade-offs:**

- One more piece of infrastructure to provision in Terraform (DynamoDB table
  + IAM role for the Lambda).
- A new runtime dependency (`boto3`).
- Two storage systems in the project (DynamoDB + Postgres), each with its own
  debugging/consistency mental model.
- Eventual-consistency read/write model in DynamoDB requires discipline
  (strongly consistent reads per item are fine at this volume).

## Not yet decided

_(original questions resolved below.)_

## Decided after acceptance

- **Item schema:** JSON blob em `data` + `version` integer; PK `chat_id` + SK `store`.
- **TTL:** 4 h (`DYNAMODB_TTL_HOURS` / `var.conversation_ttl_hours`) em
  `user_data`/`conversations`. Carrossel em `chat_data` com TTL próprio
  (`CAROUSEL_TTL_HOURS`, default 168 h).
- **Key mapping:** `user_data`/`chat_data` por id; `conversations` em PK=0.
  `bot_data` não é persistido (carrossel vive em `chat_data`).
  Conversation keys (tuplas PTB) serializadas com `json.dumps(list(key))`.
- **Application:** module-level warm reuse (`_get_application`).
- **Confirm:** insert idempotente (`find_equivalent_alert` + `created_alert_id`);
  draft apagado no sucesso; TTL cobre drafts órfãos. The `ConversationHandler`
  is `name="new_alert"` + `persistent=True`.
