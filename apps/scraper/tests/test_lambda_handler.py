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


def test_next_payload_fanned_out_non_last_slice_stops() -> None:
    """Fatia fanned-out que NÃO é a última: para ao completar."""
    nxt = lambda_handler._next_payload_after_chunk(
        {
            "listing_kind": "venda",
            "completed": True,
            "next_page": None,
            "slice_index": 0,
            "fanned_out": True,
            "run_started_at": "2026-01-01T00:00:00+00:00",
        }
    )
    assert nxt is None


def test_next_payload_fanned_out_non_last_clamped_stops() -> None:
    """Fatia fanned-out clampada que NÃO é a última: para."""
    nxt = lambda_handler._next_payload_after_chunk(
        {
            "listing_kind": "venda",
            "completed": False,
            "clamped": True,
            "next_page": None,
            "slice_index": 1,
            "fanned_out": True,
            "run_started_at": "2026-01-01T00:00:00+00:00",
        }
    )
    assert nxt is None


def test_next_payload_fanned_out_last_slice_advances_venda() -> None:
    """Última fatia de aluguel em fan-out: avança para venda."""
    last = len(lambda_handler.slices_for_kind("aluguel", "recife")) - 1
    nxt = lambda_handler._next_payload_after_chunk(
        {
            "market": "recife",
            "listing_kind": "aluguel",
            "completed": True,
            "next_page": None,
            "slice_index": last,
            "fanned_out": True,
            "run_started_at": "2026-01-01T00:00:00+00:00",
        }
    )
    assert nxt is not None
    assert nxt["listing_kind"] == "venda"
    assert nxt["slice_index"] == 0
    assert nxt["market"] == "recife"


def test_next_payload_fanned_out_last_slice_advances_market() -> None:
    """Última fatia de venda em fan-out na última cidade: para."""
    last = len(lambda_handler.slices_for_kind("venda", "natal")) - 1
    nxt = lambda_handler._next_payload_after_chunk(
        {
            "market": "natal",
            "listing_kind": "venda",
            "completed": True,
            "next_page": None,
            "slice_index": last,
            "fanned_out": True,
            "run_started_at": "2026-01-01T00:00:00+00:00",
        }
    )
    assert nxt is None


def test_next_payload_fanned_out_continues_pagination() -> None:
    """Fatia fanned-out com mais páginas: continua paginação na mesma fatia."""
    nxt = lambda_handler._next_payload_after_chunk(
        {
            "listing_kind": "venda",
            "completed": False,
            "next_page": 51,
            "slice_index": 2,
            "fanned_out": True,
            "run_started_at": "2026-01-01T00:00:00+00:00",
        }
    )
    assert nxt is not None
    assert nxt["start_page"] == 51
    assert nxt["slice_index"] == 2
    assert nxt.get("fanned_out") is True  # propagado adiante


def test_run_propagates_fanned_out_from_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    """``fanned_out=True`` no payload é propagado ao result e ao self-invoke."""
    invoked: list[dict[str, Any]] = []

    async def _fake_chunk(**kwargs: Any) -> dict[str, Any]:
        return {
            "success": 1,
            "count": 10,
            "market": "recife",
            "listing_kind": "venda",
            "slice_index": 1,
            "completed": False,
            "clamped": False,
            "next_page": 101,
            "attempt": 0,
            "run_started_at": "2026-01-01T00:00:00+00:00",
            "deactivated": 0,
        }

    monkeypatch.setattr(lambda_handler, "job_collect_chunk", _fake_chunk)
    monkeypatch.setattr(lambda_handler, "_self_invoke", invoked.append)
    monkeypatch.setattr(lambda_handler, "publish_market_snapshot", lambda: None)

    result = asyncio.run(
        lambda_handler.run(
            {
                "listing_kind": "venda",
                "market": "recife",
                "slice_index": 1,
                "fanned_out": True,
                "run_started_at": "2026-01-01T00:00:00+00:00",
            }
        )
    )

    assert result["success"] == 1
    assert len(invoked) == 1
    assert invoked[0].get("fanned_out") is True  # propagado no self-invoke


def test_run_after_fan_out_marks_main_chain_fanned_out(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Fatia 0 que disparou fan-out: continuação recebe fanned_out=True."""
    invoked: list[dict[str, Any]] = []
    fan_out_calls: list[dict[str, Any]] = []

    def _fake_invoke(payload: dict[str, Any]) -> None:
        invoked.append(payload)

    def _fake_fan_out(**kwargs: Any) -> None:
        fan_out_calls.append(kwargs)

    async def _fake_chunk(**kwargs: Any) -> dict[str, Any]:
        return {
            "success": 1,
            "count": 50,
            "market": "maceio",
            "listing_kind": "venda",
            "slice_index": 0,
            "completed": False,
            "clamped": False,
            "next_page": 101,
            "attempt": 0,
            "run_started_at": "2026-01-01T00:00:00+00:00",
            "deactivated": 0,
        }

    monkeypatch.setattr(lambda_handler, "job_collect_chunk", _fake_chunk)
    monkeypatch.setattr(lambda_handler, "_self_invoke", _fake_invoke)
    monkeypatch.setattr(lambda_handler, "_fan_out_slices", _fake_fan_out)
    monkeypatch.setattr(lambda_handler, "publish_market_snapshot", lambda: None)

    result = asyncio.run(
        lambda_handler.run(
            {
                "listing_kind": "venda",
                "market": "maceio",
                "slice_index": 0,
                "start_page": 1,
                "attempt": 0,
                "run_started_at": "2026-01-01T00:00:00+00:00",
            }
        )
    )

    assert result["success"] == 1
    # Fan-out deve ter sido chamado (Maceió venda tem 5 slices)
    assert len(fan_out_calls) == 1
    # E o self-invoke deve propagar fanned_out=True
    assert len(invoked) == 1
    assert invoked[0].get("fanned_out") is True


def test_root_logger_honors_config_level() -> None:
    expected = getattr(logging, config.LOG_LEVEL, logging.INFO)
    assert logging.getLogger().level == expected


# ── Chunk quebrado não pode matar a coleta do dia ──────────────────────────
# Causa raiz do ciclo incompleto de 03/10: a última fatia de venda do Recife
# morreu num deadlock do Postgres (`psycopg.errors.DeadlockDetected`), a cadeia
# terminou ali, Natal nunca foi visitada e nada foi inativado.


def test_falha_repete_a_fatia_sem_perder_a_pagina() -> None:
    nxt = lambda_handler._next_payload_after_failure(
        {
            "market": "recife",
            "listing_kind": "venda",
            "slice_index": 13,
            "start_page": 51,
            "attempt": 0,
            "run_started_at": "2026-01-01T00:00:00+00:00",
        }
    )
    assert nxt is not None
    assert nxt["market"] == "recife"
    assert nxt["slice_index"] == 13
    assert nxt["start_page"] == 51
    assert nxt["attempt"] == 1


def test_falha_persistente_na_ultima_fatia_ainda_abre_a_proxima_cidade() -> None:
    """Última fatia do Recife venda falhou de vez: Natal precisa rodar mesmo assim."""
    nxt = lambda_handler._next_payload_after_failure(
        {
            "market": "recife",
            "listing_kind": "venda",
            "slice_index": len(slices_for_kind("venda", "recife")) - 1,
            "start_page": 1,
            "attempt": lambda_handler.MAX_CHUNK_ATTEMPTS - 1,
            "fanned_out": True,
            "run_started_at": "2026-01-01T00:00:00+00:00",
        }
    )
    assert nxt is not None
    assert nxt["market"] == "natal"
    assert nxt["listing_kind"] == "aluguel"
    # `skip_deactivate` não viaja para o próximo mercado: a proteção de Recife
    # venda vem do placar de fatias (a fatia morta nunca marcou "ok", e sem
    # placar `fatias_pendentes` bloqueia a inativação).


def test_falha_persistente_no_meio_encerra_o_ramo_da_fatia() -> None:
    """Fatia fanned-out do meio que morreu: o ramo dela acaba (quem avança é a última).

    O que importa é que ela não marcou "ok" — a última fatia consulta o placar e
    não inativa o mercado, em vez de tirar do ar o que ninguém olhou.
    """
    nxt = lambda_handler._next_payload_after_failure(
        {
            "market": "recife",
            "listing_kind": "venda",
            "slice_index": 3,
            "start_page": 1,
            "attempt": lambda_handler.MAX_CHUNK_ATTEMPTS - 1,
            "fanned_out": True,
            "run_started_at": "2026-01-01T00:00:00+00:00",
        }
    )
    assert nxt is None


def test_run_encadeia_mesmo_quando_o_chunk_falha(monkeypatch: pytest.MonkeyPatch) -> None:
    invoked: list[dict[str, Any]] = []

    async def _chunk_quebrado(**_kwargs: Any) -> dict[str, Any]:
        return {
            "success": 0,
            "count": 0,
            "market": "recife",
            "listing_kind": "venda",
            "slice_index": 13,
            "start_page": 1,
            "attempt": 0,
            "completed": False,
            "clamped": False,
            "next_page": None,
            "run_started_at": "2026-01-01T00:00:00+00:00",
            "deactivated": 0,
        }

    monkeypatch.setattr(lambda_handler, "job_collect_chunk", _chunk_quebrado)
    monkeypatch.setattr(lambda_handler, "_self_invoke", invoked.append)

    result = asyncio.run(
        lambda_handler.run(
            {
                "listing_kind": "venda",
                "market": "recife",
                "slice_index": 13,
                "start_page": 1,
                "attempt": 0,
                "run_started_at": "2026-01-01T00:00:00+00:00",
            }
        )
    )

    assert result["success"] == 0
    assert len(invoked) == 1
    assert invoked[0]["slice_index"] == 13
    assert invoked[0]["attempt"] == 1


def test_delta_nao_entra_na_cadeia_de_fatias(monkeypatch: pytest.MonkeyPatch) -> None:
    """`mode=delta` responde e sai — sem self-invoke, sem inativar."""
    invoked: list[dict[str, Any]] = []
    visto: dict[str, Any] = {}

    async def _fake_delta(*, get_remaining_ms: Any = None) -> dict[str, Any]:
        visto["chamado"] = True
        del get_remaining_ms
        return {"success": 1, "count": 37, "delta": {"recife/venda": 37}}

    monkeypatch.setattr(lambda_handler, "_self_invoke", invoked.append)
    import scheduler.jobs as jobs

    monkeypatch.setattr(jobs, "job_collect_delta", _fake_delta)

    result = asyncio.run(lambda_handler.run({"mode": "delta"}))

    assert result["success"] == 1
    assert result["count"] == 37
    assert result["market"] == "delta"
    assert visto["chamado"] is True
    assert invoked == []
