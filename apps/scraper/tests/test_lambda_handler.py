"""Testes do entry point Lambda (lambda_handler)."""

from __future__ import annotations

from typing import Any

import pytest

import lambda_handler


def _patch_run(monkeypatch: pytest.MonkeyPatch, result: Any) -> None:
    async def _fake(event=None, *, get_remaining_ms=None) -> Any:
        del event, get_remaining_ms
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


def test_next_payload_continues_same_kind() -> None:
    nxt = lambda_handler._next_payload_after_chunk(
        {
            "listing_kind": "venda",
            "completed": False,
            "next_page": 51,
            "run_started_at": "2026-01-01T00:00:00+00:00",
        }
    )
    assert nxt == {
        "listing_kind": "venda",
        "start_page": 51,
        "run_started_at": "2026-01-01T00:00:00+00:00",
    }


def test_next_payload_starts_venda_after_aluguel_complete() -> None:
    nxt = lambda_handler._next_payload_after_chunk(
        {
            "listing_kind": "aluguel",
            "completed": True,
            "next_page": None,
            "run_started_at": "2026-01-01T00:00:00+00:00",
        }
    )
    assert nxt is not None
    assert nxt["listing_kind"] == "venda"
    assert nxt["start_page"] == 1
    assert nxt["run_started_at"] is None


def test_next_payload_none_when_venda_complete() -> None:
    nxt = lambda_handler._next_payload_after_chunk(
        {
            "listing_kind": "venda",
            "completed": True,
            "next_page": None,
            "run_started_at": "2026-01-01T00:00:00+00:00",
        }
    )
    assert nxt is None
