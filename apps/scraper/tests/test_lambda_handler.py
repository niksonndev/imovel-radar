"""Testes do entry point Lambda (lambda_handler)."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import pytest

import config
import lambda_handler
from scheduler.jobs import slices_for_kind


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
        "market": "maceio",
        "listing_kind": "venda",
        "slice_index": 0,
        "start_page": 51,
        "attempt": 0,
        "run_started_at": "2026-01-01T00:00:00+00:00",
    }


def test_next_payload_keeps_attempt_when_retrying_page() -> None:
    nxt = lambda_handler._next_payload_after_chunk(
        {
            "listing_kind": "aluguel",
            "completed": False,
            "next_page": 4,
            "slice_index": 0,
            "attempt": 2,
            "run_started_at": "2026-01-01T00:00:00+00:00",
        }
    )
    assert nxt is not None
    assert nxt["start_page"] == 4
    assert nxt["attempt"] == 2
    assert nxt["slice_index"] == 0


def test_next_payload_starts_venda_after_aluguel_complete() -> None:
    nxt = lambda_handler._next_payload_after_chunk(
        {
            "listing_kind": "aluguel",
            "completed": True,
            "next_page": None,
            "run_started_at": "2026-01-01T00:00:00+00:00",
        }
    )
    assert nxt == {
        "market": "maceio",
        "listing_kind": "venda",
        "slice_index": 0,
        "start_page": 1,
        "attempt": 0,
        "run_started_at": None,
    }


def test_next_payload_advances_venda_slice_same_watermark() -> None:
    nxt = lambda_handler._next_payload_after_chunk(
        {
            "listing_kind": "venda",
            "completed": True,
            "next_page": None,
            "slice_index": 1,
            "run_started_at": "2026-01-01T00:00:00+00:00",
        }
    )
    assert nxt == {
        "market": "maceio",
        "listing_kind": "venda",
        "slice_index": 2,
        "start_page": 1,
        "attempt": 0,
        "run_started_at": "2026-01-01T00:00:00+00:00",
    }


def test_next_payload_opens_recife_after_maceio_venda() -> None:
    last = len(slices_for_kind("venda", "maceio")) - 1
    nxt = lambda_handler._next_payload_after_chunk(
        {
            "market": "maceio",
            "listing_kind": "venda",
            "completed": True,
            "next_page": None,
            "slice_index": last,
            "run_started_at": "2026-01-01T00:00:00+00:00",
        }
    )
    assert nxt == {
        "market": "recife",
        "listing_kind": "aluguel",
        "slice_index": 0,
        "start_page": 1,
        "attempt": 0,
        "run_started_at": None,
    }


def test_next_payload_opens_natal_after_recife_venda() -> None:
    last = len(slices_for_kind("venda", "recife")) - 1
    nxt = lambda_handler._next_payload_after_chunk(
        {
            "market": "recife",
            "listing_kind": "venda",
            "completed": True,
            "next_page": None,
            "slice_index": last,
            "run_started_at": "2026-01-01T00:00:00+00:00",
        }
    )
    assert nxt == {
        "market": "natal",
        "listing_kind": "aluguel",
        "slice_index": 0,
        "start_page": 1,
        "attempt": 0,
        "run_started_at": None,
    }


def test_next_payload_none_when_last_natal_venda_slice_complete() -> None:
    last = len(slices_for_kind("venda", "natal")) - 1
    nxt = lambda_handler._next_payload_after_chunk(
        {
            "market": "natal",
            "listing_kind": "venda",
            "completed": True,
            "next_page": None,
            "slice_index": last,
            "run_started_at": "2026-01-01T00:00:00+00:00",
        }
    )
    assert nxt is None


def test_next_payload_clamp_advances_slice_without_deactivate_flag_lost() -> None:
    nxt = lambda_handler._next_payload_after_chunk(
        {
            "market": "recife",
            "listing_kind": "venda",
            "completed": False,
            "clamped": True,
            "next_page": None,
            "slice_index": 1,
            "run_started_at": "2026-01-01T00:00:00+00:00",
        }
    )
    assert nxt == {
        "market": "recife",
        "listing_kind": "venda",
        "slice_index": 2,
        "start_page": 1,
        "attempt": 0,
        "run_started_at": "2026-01-01T00:00:00+00:00",
        "skip_deactivate": True,
    }


def test_smoke_does_not_self_invoke_or_deactivate(monkeypatch: pytest.MonkeyPatch) -> None:
    invoked: list[dict[str, Any]] = []
    published: list[bool] = []

    async def _fake_chunk(**kwargs: Any) -> dict[str, Any]:
        assert kwargs["skip_deactivate"] is True
        assert kwargs["max_pages"] == 2
        return {
            "success": 1,
            "count": 80,
            "market": "maceio",
            "listing_kind": "aluguel",
            "slice_index": 0,
            "completed": False,
            "clamped": False,
            "next_page": 3,
            "attempt": 0,
            "run_started_at": "2026-01-01T00:00:00+00:00",
            "deactivated": 0,
        }

    monkeypatch.setattr(lambda_handler, "job_collect_chunk", _fake_chunk)
    monkeypatch.setattr(lambda_handler, "_self_invoke", invoked.append)
    monkeypatch.setattr(lambda_handler, "publish_market_snapshot", lambda: published.append(True))

    result = asyncio.run(lambda_handler.run({"smoke": True, "listing_kind": "aluguel"}))

    assert result["success"] == 1
    assert result["count"] == 80
    assert invoked == []
    assert published == []


def test_root_logger_honors_config_level() -> None:
    expected = getattr(logging, config.LOG_LEVEL, logging.INFO)
    assert logging.getLogger().level == expected
