# Migration: standalone APScheduler → PTB's native JobQueue

**Date:** 2026-07-19

## Why

The project used `BackgroundScheduler` (APScheduler) running on a
thread separate from the bot's main thread. This required a manual
bridge between threads whenever the job needed to send Telegram
messages (`asyncio.run_coroutine_threadsafe(coroutine, loop).result(timeout=...)`),
since the scheduler thread had no event loop of its own.

`python-telegram-bot`'s native `job_queue` runs inside the SAME event
loop as the bot — it removes the cross-thread bridge, and the job
becomes a regular coroutine (`await` directly).

## Dependency: optional extra, not a separate package

`JobQueue` requires the PTB `[job-queue]` extra: python-telegram-bot[job-queue]>=21.0

Without it, `app.job_queue` comes back as `None` at runtime (the error
only shows up when calling `run_daily`/`run_once`, not at startup).

Internally this extra uses `apscheduler.AsyncIOScheduler` — meaning
`apscheduler` remains in the environment as a transitive dependency of
PTB. The standalone `apscheduler>=3.10.0` line was removed from
requirements.txt because it became redundant (no direct `apscheduler`
import remains in the codebase after the migration) — the package
itself is still installed and still required.

## Pattern: sync scrape inside an async loop

`_do_full_scrape` is synchronous and blocking (network + SQLite).
Running it directly inside the job_queue (same loop as the bot) would
freeze the whole bot for the duration of the scrape — no commands would
be answered.

Fix: `await asyncio.to_thread(_do_full_scrape)` inside `job_daily`.
Same pattern already used in `main.py` (`post_init`) for
`run_initial_scrape`. Manually validated: during a ~5-6 min scrape, the
bot responded to `/start` normally in the middle of the run.

## Manually computed "next run" for logging

`job_queue.run_daily(...)` doesn't expose `next_run_time` right after
registration (the underlying `Job` only populates that once the
JobQueue actually starts, which happens after `post_init` returns).
Because of that, `scheduler/setup.py` computes the next run time
manually (today or tomorrow, depending on whether the configured time
already passed) purely for logging — actual scheduling doesn't depend
on this calculation.

## See also

- `docs/scheduler/admin-alerts.md` — feature that runs inside this same job_daily
