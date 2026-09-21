from __future__ import annotations

import base64
import json

import config
import lambda_handler


def test_eventbridge_detection() -> None:
    assert lambda_handler._is_eventbridge({"source": "aws.events"})
    assert lambda_handler._is_eventbridge({"detail-type": "Scheduled Event"})
    assert not lambda_handler._is_eventbridge({"body": "{}"})


def test_webhook_secret_rejects_missing_and_wrong(monkeypatch) -> None:
    monkeypatch.setattr(config, "TELEGRAM_WEBHOOK_SECRET", "s3cret-token-value")
    assert not lambda_handler.webhook_secret_ok({"headers": {}})
    assert not lambda_handler.webhook_secret_ok(
        {"headers": {"x-telegram-bot-api-secret-token": "nope"}}
    )
    assert lambda_handler.webhook_secret_ok(
        {"headers": {"X-Telegram-Bot-Api-Secret-Token": "s3cret-token-value"}}
    )


def test_webhook_secret_fail_closed_when_unset(monkeypatch) -> None:
    monkeypatch.setattr(config, "TELEGRAM_WEBHOOK_SECRET", "")
    assert not lambda_handler.webhook_secret_ok(
        {"headers": {"x-telegram-bot-api-secret-token": ""}}
    )


def test_lambda_handler_rejects_unauthorized_webhook(monkeypatch) -> None:
    monkeypatch.setattr(config, "TELEGRAM_WEBHOOK_SECRET", "expected")
    result = lambda_handler.lambda_handler({"body": "{}"}, None)
    assert result["statusCode"] == 403


def test_decode_event_body_handles_base64() -> None:
    raw = json.dumps({"update_id": 1})
    event = {
        "isBase64Encoded": True,
        "body": base64.b64encode(raw.encode()).decode(),
    }
    assert lambda_handler.decode_event_body(event) == raw
