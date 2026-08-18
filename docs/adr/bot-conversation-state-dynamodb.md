# 0006 - Bot conversation state persisted in DynamoDB (PTB BasePersistence)

## Status

Accepted

## Context

With webhook + Lambda (ADR 0004), the bot has no continuous process, so state
that lives in a long-running process disappears. Today the bot persists
conversation state in a local file via
`PicklePersistence(carousel_state.pickle)`: `user_data` (the wizard draft and
the wizard UI state), `chat_data`, `bot_data` (carousel navigation) and
`conversation_data` (the `ConversationHandler` current-state pointer).

The `/novo_alerta` flow is a multi-step `ConversationHandler`
(`PRICE → NEIGHBOURHOODS → NAME → CONFIRM`); every step depends on the
previous one. The carousel, sent after an alert is created or when matches
are found, stores its listings in `bot_data` so "next/prev" navigation can
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

The persistence backend stores `user_data`, `chat_data`, `conversation_data`
and `bot_data` (carousel included), keyed by `chat_id`.

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
- The **carousel is included** via the same `bot_data` persistence, so
  navigation survives cold starts and concurrent invocations.
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

1. Exact item schema — full JSON blob of the PTB data vs. separate attributes
   — and the semantics of the `version`/`updated_at` attribute.
2. TTL value (proposed 2–6 h, aligned with human conversation pacing; the
   handler already answers "Sessão expirada").
3. Mapping of the PTB stores (`user_data`/`chat_data`/`bot_data`/
   `conversation_data`) to DynamoDB keys, and whether the full payload
   (including `neighbourhood_options`) is persisted.
4. `Application` instantiation inside the Lambda (module-level warm reuse vs.
   per-invocation) and its interplay with the persistence backend.
5. Confirm-flow cleanup semantics: idempotent insert + draft deletion; what
   happens when the insert succeeds but the draft deletion fails (TTL as the
   safety net).
