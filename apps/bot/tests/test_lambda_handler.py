from __future__ import annotations

import asyncio
import base64
import json

import config
import lambda_handler


def test_eventbridge_detection() -> None:
    assert lambda_handler._is_eventbridge({"source": "aws.events"})
    assert lambda_handler._is_eventbridge({"detail-type": "Scheduled Event"})
    assert not lambda_handler._is_eventbridge({"body": "{}"})


def test_notify_dry_run_from_detail() -> None:
    assert lambda_handler._is_notify_dry_run(
        {"source": "aws.events", "detail": {"dry_run": True}}
    )
    assert not lambda_handler._is_notify_dry_run(
        {"source": "aws.events", "detail": {"dry_run": "yes"}}
    )
    assert not lambda_handler._is_notify_dry_run(
        {"source": "aws.events", "detail": {"dry_run": False}}
    )
    assert not lambda_handler._is_notify_dry_run({"source": "aws.events"})
    assert not lambda_handler._is_notify_dry_run(
        {"source": "aws.events", "detail": "not-a-dict"}
    )


def test_lambda_handler_eventbridge_passes_dry_run(monkeypatch) -> None:
    seen: dict[str, bool] = {}

    async def fake_handle_notify(*, dry_run: bool = False) -> None:
        seen["dry_run"] = dry_run

    monkeypatch.setattr(lambda_handler, "_handle_notify", fake_handle_notify)
    result = lambda_handler.lambda_handler(
        {
            "source": "aws.events",
            "detail-type": "Scheduled Event",
            "detail": {"dry_run": True},
        },
        None,
    )
    assert result["statusCode"] == 200
    assert seen == {"dry_run": True}


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


def test_persistent_loop_survives_multiple_runs() -> None:
    """asyncio.run fecharia o loop; o helper deve reutilizar o mesmo."""
    loop1 = lambda_handler._get_loop()
    assert not loop1.is_closed()
    result = lambda_handler._run(asyncio.sleep(0, result=42))
    assert result == 42
    loop2 = lambda_handler._get_loop()
    assert loop1 is loop2
    assert not loop2.is_closed()
