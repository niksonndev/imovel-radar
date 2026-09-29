import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import handlers.email_pro_trial as email_trial
import handlers.privacy as privacy


def _callback_update(data: str):
    query = MagicMock()
    query.data = data
    query.answer = AsyncMock()
    query.edit_message_text = AsyncMock()
    update = MagicMock()
    update.callback_query = query
    update.effective_user = MagicMock(id=123)
    return update, query


def test_privacy_delete_request_requires_confirmation() -> None:
    message = MagicMock()
    message.reply_text = AsyncMock()
    update = MagicMock()
    update.effective_message = message
    context = MagicMock()
    context.user_data = {
        "create_alert_draft": {"max_price": 2000},
        "assistant_pending_alert": {"max_price": 2000},
    }

    result = asyncio.run(privacy.privacy_delete_request(update, context))

    assert result == -1
    assert "create_alert_draft" not in context.user_data
    assert "assistant_pending_alert" not in context.user_data
    token = context.user_data["pending_data_deletion_token"]
    markup = message.reply_text.call_args.kwargs["reply_markup"]
    assert markup.inline_keyboard[0][0].callback_data == f"privacy_delete_yes_{token}"


def test_privacy_delete_cancel_keeps_data() -> None:
    token = "012345abcdef"
    update, query = _callback_update(f"privacy_delete_no_{token}")
    context = MagicMock()
    context.user_data = {"pending_data_deletion_token": token, "assistant_history": []}

    asyncio.run(privacy.privacy_delete_confirm_cb(update, context))

    assert "assistant_history" in context.user_data
    assert "pending_data_deletion_token" not in context.user_data
    assert "mantidos" in query.edit_message_text.call_args.args[0]


def test_privacy_delete_confirm_purges_user_data(monkeypatch) -> None:
    token = "012345abcdef"
    update, query = _callback_update(f"privacy_delete_yes_{token}")
    context = MagicMock()
    context.user_data = {"pending_data_deletion_token": token, "assistant_history": []}
    context.application.persistence.purge_user_records = AsyncMock()
    monkeypatch.setattr(
        privacy,
        "get_user",
        AsyncMock(return_value=SimpleNamespace(stars_subscription_active=False)),
    )
    delete = AsyncMock(return_value=True)
    monkeypatch.setattr(privacy, "delete_user_data", delete)

    asyncio.run(privacy.privacy_delete_confirm_cb(update, context))

    delete.assert_awaited_once_with(123)
    context.application.persistence.purge_user_records.assert_awaited_once_with(123)
    assert context.user_data == {}
    assert "excluídos" in query.edit_message_text.call_args.args[0]


def test_privacy_delete_cancels_stars_before_deleting(monkeypatch) -> None:
    token = "012345abcdef"
    update, query = _callback_update(f"privacy_delete_yes_{token}")
    context = MagicMock()
    context.user_data = {"pending_data_deletion_token": token}
    context.application.persistence.purge_user_records = AsyncMock()
    context.bot.edit_user_star_subscription = AsyncMock()
    user = SimpleNamespace(
        stars_subscription_active=True,
        stars_telegram_payment_charge_id="charge",
    )
    monkeypatch.setattr(privacy, "get_user", AsyncMock(return_value=user))
    canceled = AsyncMock()
    monkeypatch.setattr(privacy, "mark_pro_subscription_canceled", canceled)
    delete = AsyncMock(return_value=True)
    monkeypatch.setattr(privacy, "delete_user_data", delete)

    asyncio.run(privacy.privacy_delete_confirm_cb(update, context))

    context.bot.edit_user_star_subscription.assert_awaited_once_with(
        user_id=123,
        telegram_payment_charge_id="charge",
        is_canceled=True,
    )
    canceled.assert_awaited_once_with(123)
    delete.assert_awaited_once_with(123)


def test_email_trial_audio_keeps_trial_waiting() -> None:
    message = MagicMock()
    message.reply_text = AsyncMock()
    update = MagicMock()
    update.effective_message = message

    result = asyncio.run(email_trial.email_pro_trial_audio(update, MagicMock()))

    assert result == email_trial.ASK_EMAIL
    assert "por texto" in message.reply_text.call_args.args[0]
