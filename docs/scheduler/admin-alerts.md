# Admin alerts on scrape failure

**Date:** 2026-07-19

## Why

The daily scrape (`job_daily`) used to fail silently: an exception or
an empty result (0 listings) would just get logged, with no signal
outside the log file. The only way to notice was indirectly — users
stop getting new-listing notifications, and that's easy to miss for
days.

## What triggers an alert

Sent to `ADMIN_CHAT_ID` (Telegram) when the scrape either:

- raises an exception, or
- succeeds but returns 0 listings (likely OLX blocking or a page
  structure change — same failure mode as the RSC migration, see
  `olx-rsc-migration.md`)

Not triggered when the scrape succeeds with `count > 0` but simply has
0 _new_ matches for a given alert — that's expected/normal, not a
scraper problem, and alerting on it would just be noise.

## Behavior difference between the two cases

- **Exception** → notifications to users are skipped entirely (nothing
  new was persisted, so there's nothing to match against safely)
- **0 listings, no exception** → notifications still run normally. An
  empty scrape shouldn't block matching against listings already in
  the DB from previous runs.

## Implementation notes

- `_do_full_scrape` returns `(success: bool, count: int)` instead of
  just `bool`, so `job_daily` can tell "crashed" apart from "ran but
  empty".
- `job_daily` runs on the `BackgroundScheduler` thread (sync, no event
  loop). The admin-alert coroutine runs on the PTB thread's loop via
  `run_coroutine_threadsafe(...).result(timeout=...)` — same bridging
  pattern already used for `_notify_new_matches_all_alerts`.
- Admin alerts use a short, dedicated timeout
  (`_ADMIN_ALERT_TIMEOUT_SECONDS`), separate from
  `_NOTIFY_TIMEOUT_SECONDS`. The notify timeout is long because it
  loops over every active alert; an admin alert is a single message
  and shouldn't be able to block the thread for minutes if Telegram is
  slow.
- Sending the admin alert itself never raises — a failure there is
  logged and swallowed, so a broken alert path can't take down the
  rest of `job_daily`.
