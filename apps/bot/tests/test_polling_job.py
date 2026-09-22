"""Tests for daily notify dry-run (smoke) behaviour."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from shared_models.tables import ListingAlertMatch

from jobs import polling_job


def test_process_chat_dry_run_skips_send_and_mark(monkeypatch) -> None:
    listing = SimpleNamespace(listing_id=99, title="Apt")
    rows = [ListingAlertMatch(listing=listing, alert_id=7)]  # type: ignore[arg-type]

    send = AsyncMock()
    mark = AsyncMock()
    monkeypatch.setattr(polling_job, "get_unnotified_listings", AsyncMock(return_value=rows))
    monkeypatch.setattr(polling_job, "send_carousel", send)
    monkeypatch.setattr(polling_job, "mark_listings_notified", mark)

    app = SimpleNamespace(bot=object(), bot_data={})
    asyncio.run(polling_job._process_chat(42, app, dry_run=True))  # type: ignore[arg-type]

    send.assert_not_called()
    mark.assert_not_called()


def test_process_chat_sends_and_marks_when_not_dry_run(monkeypatch) -> None:
    listing = SimpleNamespace(listing_id=99, title="Apt")
    rows = [ListingAlertMatch(listing=listing, alert_id=7)]  # type: ignore[arg-type]

    send = AsyncMock()
    mark = AsyncMock()
    monkeypatch.setattr(polling_job, "get_unnotified_listings", AsyncMock(return_value=rows))
    monkeypatch.setattr(polling_job, "send_carousel", send)
    monkeypatch.setattr(polling_job, "mark_listings_notified", mark)

    app = SimpleNamespace(bot=object(), bot_data={})
    asyncio.run(polling_job._process_chat(42, app, dry_run=False))  # type: ignore[arg-type]

    send.assert_awaited_once()
    mark.assert_awaited_once_with(42, [(7, 99)])


def test_notify_new_matches_dry_run_skips_telegram_sleep(monkeypatch) -> None:
    process = AsyncMock()
    sleep = AsyncMock()
    monkeypatch.setattr(polling_job, "list_all_users", lambda: [1, 2])
    monkeypatch.setattr(polling_job, "_process_chat", process)
    monkeypatch.setattr(polling_job.asyncio, "sleep", sleep)

    app = SimpleNamespace()
    asyncio.run(polling_job.notify_new_matches(app, dry_run=True))  # type: ignore[arg-type]

    assert process.await_count == 2
    assert process.await_args_list[0].kwargs["dry_run"] is True
    sleep.assert_not_called()
