"""Unit tests for Stars checkout handlers (mocked Telegram objects)."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import config
from handlers import billing


def test_pro_precheckout_ok(monkeypatch) -> None:
    monkeypatch.setattr(config, "PRO_STARS_AMOUNT", 200)
    query = MagicMock()
    query.invoice_payload = "pro_monthly:99"
    query.from_user.id = 99
    query.currency = "XTR"
    query.total_amount = 200
    query.answer = AsyncMock()
    update = MagicMock()
    update.pre_checkout_query = query

    asyncio.run(billing.pro_precheckout(update, MagicMock()))
    query.answer.assert_awaited_once_with(ok=True)


def test_pro_precheckout_rejects_wrong_amount(monkeypatch) -> None:
    monkeypatch.setattr(config, "PRO_STARS_AMOUNT", 200)
    query = MagicMock()
    query.invoice_payload = "pro_monthly:99"
    query.from_user.id = 99
    query.currency = "XTR"
    query.total_amount = 50
    query.answer = AsyncMock()
    update = MagicMock()
    update.pre_checkout_query = query

    asyncio.run(billing.pro_precheckout(update, MagicMock()))
    query.answer.assert_awaited_once()
    kwargs = query.answer.await_args.kwargs
    assert kwargs["ok"] is False


def test_pro_successful_payment_activates(monkeypatch) -> None:
    monkeypatch.setattr(config, "PRO_SUBSCRIPTION_PERIOD_SECONDS", 2592000)
    until = datetime.now(UTC) + timedelta(days=30)
    activate = AsyncMock()
    monkeypatch.setattr(billing, "activate_pro", activate)

    payment = SimpleNamespace(
        invoice_payload="pro_monthly:77",
        subscription_expiration_date=until,
        telegram_payment_charge_id="tg_charge_1",
        is_recurring=False,
    )
    message = MagicMock()
    message.successful_payment = payment
    message.reply_text = AsyncMock()
    update = MagicMock()
    update.effective_message = message
    update.effective_user = SimpleNamespace(id=77)

    asyncio.run(billing.pro_successful_payment(update, MagicMock()))

    activate.assert_awaited_once()
    kwargs = activate.await_args.kwargs
    assert kwargs["chat_id"] == 77
    assert kwargs["telegram_payment_charge_id"] == "tg_charge_1"
    assert kwargs["subscription_active"] is True
    message.reply_text.assert_awaited()
