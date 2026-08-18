"""Testes do entry point Lambda (lambda_handler)."""

from __future__ import annotations

from typing import Any

import pytest

import lambda_handler


def _patch_run(monkeypatch: pytest.MonkeyPatch, result: Any) -> None:
    async def _fake() -> Any:
        if isinstance(result, Exception):
            raise result
        return result

    monkeypatch.setattr(lambda_handler, "run", _fake)


def test_lambda_handler_returns_job_result(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_run(monkeypatch, {"success": 1, "count": 4})

    result = lambda_handler.lambda_handler({}, None)

    assert result == {"success": 1, "count": 4}


def test_lambda_handler_returns_failure_on_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_run(monkeypatch, RuntimeError("boom"))

    result = lambda_handler.lambda_handler({}, None)

    assert result == {"success": 0, "count": 0}


def test_lambda_handler_accepts_eventbridge_event(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_run(monkeypatch, {"success": 1, "count": 0})
    event = {"source": "aws.events", "detail-type": "Scheduled Event", "detail": {}}

    result = lambda_handler.lambda_handler(event)

    assert result["success"] == 1
