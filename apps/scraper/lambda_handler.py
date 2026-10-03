"""Entry point AWS Lambda para o scraper (trigger: EventBridge + self-invoke).

Executa um chunk de coleta OLX + persistência. Se ainda houver páginas (ou o
próximo ``listing_kind``), auto-invoca a mesma função com o cursor. Nunca roda
migrations (Alembic é step do pipeline — ADR 0004) e não importa o FastAPI.

Event payload (EventBridge ou self-invoke)::

    {
      "market": "maceio" | "recife" | "natal",
      "listing_kind": "aluguel" | "venda",
      "slice_index": 0,
      "start_page": 1,
      "attempt": 0,
      "skip_deactivate": false,
      "run_started_at": "<iso8601>",
      "smoke": false,
      "fanned_out": false
    }

``smoke: true`` (CI): poucas páginas, sem deactivate, sem self-invoke, sem snapshot.
``fanned_out`` é True nas fatias 1..N (invocadas em paralelo) e na continuação
da fatia 0 depois do fan-out. Quando True, a chain NUNCA avança para a próxima
fatia — só a última fatia do kind avança para o próximo kind/market.

Run manual/local (coleta aluguel completa)::

    uv run python -m scheduler.jobs
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any

import config
from scheduler.jobs import (
    job_collect_chunk,
    normalize_kind,
    parse_run_started_at,
    slices_for_kind,
)
from stats.publish import publish_market_snapshot

# O runtime da Lambda já configura o root logger (basicConfig vira no-op)
# e o nível fica acima de INFO. Força o nível para os logs da coleta aparecerem.
_LOG_LEVEL = getattr(logging, config.LOG_LEVEL, logging.INFO)
logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=_LOG_LEVEL,
    force=True,
)
logging.getLogger().setLevel(_LOG_LEVEL)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

# Tentativas de uma fatia antes de seguir a cadeia sem ela.
MAX_CHUNK_ATTEMPTS = 3


def _event_payload(event: dict | None) -> dict[str, Any]:
    if not event:
        return {}
    # EventBridge may wrap custom input under "detail"
    detail = event.get("detail")
    if isinstance(detail, dict) and (
        "listing_kind" in detail
        or "start_page" in detail
        or "run_started_at" in detail
        or "slice_index" in detail
        or "market" in detail
        or "smoke" in detail
        or "mode" in detail
    ):
        return detail
    return event


def _self_invoke(payload: dict[str, Any]) -> None:
    """Async self-invoke of this Lambda with the next cursor."""
    function_name = os.environ.get("AWS_LAMBDA_FUNCTION_NAME")
    if not function_name:
        logger.warning("AWS_LAMBDA_FUNCTION_NAME ausente — skip self-invoke: %s", payload)
        return
    try:
        import boto3  # type: ignore[import-not-found]
    except ImportError:
        logger.exception("boto3 indisponível — skip self-invoke")
        return

    client = boto3.client("lambda")  # type: ignore[attr-defined]
    client.invoke(
        FunctionName=function_name,
        InvocationType="Event",
        Payload=json.dumps(payload).encode("utf-8"),
    )
    logger.info("Self-invoke enfileirado: %s", payload)


def _fan_out_slices(
    *,
    market: str,
    listing_kind: str,
    run_started_at: str | None,
    skip_deactivate: bool,
    current_slice: int,
) -> None:
    """Invoca assincronamente todas as OUTRAS fatias deste kind em paralelo.

    Chamado apenas na fatia 0 (slice_index=0, attempt=0, start_page=1) ao iniciar um kind.
    As fatias invocadas rodam independentemente com suas próprias cadeias de self-invoke.
    """
    function_name = os.environ.get("AWS_LAMBDA_FUNCTION_NAME")
    if not function_name:
        logger.warning("AWS_LAMBDA_FUNCTION_NAME ausente — skip fan-out")
        return
    try:
        import boto3  # type: ignore[import-not-found]
    except ImportError:
        logger.exception("boto3 indisponível — skip fan-out")
        return

    from scheduler.jobs import slices_for_kind

    total_slices = len(slices_for_kind(listing_kind, market))  # type: ignore[arg-type]
    if total_slices <= 1:
        return

    client = boto3.client("lambda")  # type: ignore[attr-defined]
    for si in range(current_slice + 1, total_slices):
        payload = _cursor(
            market=market,
            listing_kind=listing_kind,
            slice_index=si,
            start_page=1,
            attempt=0,
            run_started_at=run_started_at,
            skip_deactivate=skip_deactivate,
            fanned_out=True,
        )
        client.invoke(
            FunctionName=function_name,
            InvocationType="Event",
            Payload=json.dumps(payload).encode("utf-8"),
        )
        logger.info("Fan-out fatia %s/%s enfileirada: %s", si, total_slices - 1, payload)


def _cursor(
    *,
    market: str,
    listing_kind: str,
    slice_index: int,
    start_page: int,
    attempt: int,
    run_started_at: str | None,
    skip_deactivate: bool,
    fanned_out: bool = False,
    price_min: int | None = None,
    price_max: int | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "market": market,
        "listing_kind": listing_kind,
        "slice_index": slice_index,
        "start_page": start_page,
        "attempt": attempt,
        "run_started_at": run_started_at,
    }
    # Faixa explícita = fatia filha (nascida de uma fatia que clampou). A faixa
    # viaja no payload porque a filha não existe no config.
    if price_min is not None:
        payload["price_min"] = price_min
    if price_max is not None:
        payload["price_max"] = price_max
    if skip_deactivate:
        payload["skip_deactivate"] = True
    if fanned_out:
        payload["fanned_out"] = True
    return payload


def _is_market_stats_request(event: dict | None) -> bool:
    if not isinstance(event, dict):
        return False
    request_context = event.get("requestContext")
    if not isinstance(request_context, dict):
        return False
    http = request_context.get("http")
    if not isinstance(http, dict):
        return False
    method = str(http.get("method") or "").upper()
    path = str(http.get("path") or event.get("rawPath") or "")
    return method == "GET" and path.rstrip("/").endswith("/market-stats")


def _should_publish_snapshot(result: dict[str, Any]) -> bool:
    """True só no último chunk da última cidade (venda de Natal concluída).

    ``_next_payload_after_chunk`` também devolve None quando a fatia quebra
    no meio. Esse caso não publica — o snapshot anterior fica no ar.
    """
    if not result.get("success"):
        return False
    if _next_payload_after_chunk(result) is not None:
        return False
    if not (result.get("completed") or result.get("clamped")):
        return False
    if result.get("listing_kind") != "venda":
        return False
    market = str(result.get("market") or "maceio")
    if config.next_market(market) is not None:
        return False
    last_slice = len(slices_for_kind("venda", market)) - 1
    return int(result.get("slice_index") or 0) == last_slice


def _next_payload_after_failure(result: dict[str, Any]) -> dict[str, Any] | None:
    """Chunk quebrou (deadlock no banco, HTML inesperado, erro de rede).

    Repete a mesma fatia algumas vezes; persistindo o erro, **segue a cadeia
    como se a OLX tivesse clampado** — sem inativar.

    Antes disso, um erro matava a coleta do dia: a última fatia de venda do
    Recife morreu num deadlock e a cadeia nunca chegou a Natal (nem inativou o
    que saiu do ar). A nota do docstring de ``_should_publish_snapshot`` sobre
    "quebrar no meio não publica" era exatamente esse buraco.
    """
    attempt = int(result.get("attempt") or 0)
    if attempt + 1 < MAX_CHUNK_ATTEMPTS:
        return _cursor(
            market=str(result.get("market") or "maceio"),
            listing_kind=str(result.get("listing_kind") or "aluguel"),
            slice_index=int(result.get("slice_index") or 0),
            start_page=int(result.get("start_page") or 1),
            attempt=attempt + 1,
            run_started_at=result.get("run_started_at"),
            skip_deactivate=bool(result.get("skip_deactivate")),
            fanned_out=bool(result.get("fanned_out")),
        )
    fallback = dict(result)
    fallback.update(
        {"clamped": True, "completed": False, "next_page": None, "skip_deactivate": True}
    )
    logger.warning(
        "Fatia %s (market=%s kind=%s) falhou %s vezes — seguindo a cadeia sem inativar",
        result.get("slice_index"),
        result.get("market"),
        result.get("listing_kind"),
        MAX_CHUNK_ATTEMPTS,
    )
    return _next_payload_after_chunk(fallback)


def _next_payload_after_chunk(result: dict[str, Any]) -> dict[str, Any] | None:
    """Próximo cursor: mais páginas, próxima fatia (só se não fanned-out),
    venda, ou a próxima cidade.

    A watermark (``run_started_at``) não muda entre fatias do mesmo kind.
    Zera ao abrir a venda ou outra cidade, para o deactivate não misturar coletas.
    Um clamp da OLX encerra a fatia sem ``completed`` e impede o deactivate
    daquele kind; a cadeia segue para a próxima fatia ou cidade.

    **Fan-out mode** (``fanned_out=True``): a cadeia NUNCA avança para a
    próxima fatia — só a última fatia do kind avança para o próximo
    kind/market. Isto elimina a cascata combinacional que ocorria quando a
    chain principal (fatia 0) prosseguia pelas fatias seguintes enquanto o
    fan-out já as havia invocado em paralelo.
    """
    kind = result["listing_kind"]
    market = str(result.get("market") or "maceio")
    run_started_at = result["run_started_at"]
    slice_index = int(result.get("slice_index") or 0)
    attempt = int(result.get("attempt") or 0)
    skip_deactivate = bool(result.get("skip_deactivate"))
    clamped = bool(result.get("clamped"))
    fanned_out = bool(result.get("fanned_out"))

    if not result.get("completed") and result.get("next_page") and not clamped:
        return _cursor(
            market=market,
            listing_kind=kind,
            slice_index=slice_index,
            start_page=int(result["next_page"]),
            attempt=attempt,
            run_started_at=run_started_at,
            skip_deactivate=skip_deactivate,
            fanned_out=fanned_out,
        )

    slice_finished = bool(result.get("completed")) or clamped
    if not slice_finished:
        return None

    if clamped:
        skip_deactivate = True

    total = len(slices_for_kind(kind, market))

    # Fan-out mode: só a última fatia avança (para o próximo kind/market).
    # As fatias intermediárias param aqui — suas congêneres já foram
    # invocadas em paralelo pelo fan-out e seguem suas próprias cadeias.
    if fanned_out and slice_index < total - 1:
        return None

    next_slice = slice_index + 1
    if next_slice < total:
        return _cursor(
            market=market,
            listing_kind=kind,
            slice_index=next_slice,
            start_page=1,
            attempt=0,
            run_started_at=run_started_at,
            skip_deactivate=skip_deactivate,
        )

    if kind == "aluguel":
        # Nova watermark para a venda (não misturar com o aluguel).
        return _cursor(
            market=market,
            listing_kind="venda",
            slice_index=0,
            start_page=1,
            attempt=0,
            run_started_at=None,
            skip_deactivate=False,
        )

    nxt = config.next_market(market)
    if nxt is None:
        return None
    return _cursor(
        market=nxt.key,
        listing_kind="aluguel",
        slice_index=0,
        start_page=1,
        attempt=0,
        run_started_at=None,
        skip_deactivate=False,
    )


async def run(
    event: dict | None = None,
    *,
    get_remaining_ms: Any = None,
) -> dict[str, Any]:
    payload = _event_payload(event)

    # Passada curta por recência (regra horária): pega o que é novo e NÃO
    # inativa nada. Não entra na cadeia de fatias — é uma invocação curta e
    # independente da varredura completa.
    if payload.get("mode") == "delta":
        from scheduler.jobs import job_collect_delta

        resultado = await job_collect_delta(get_remaining_ms=get_remaining_ms)
        return {
            "success": resultado.get("success", 0),
            "count": resultado.get("count", 0),
            "market": "delta",
            "listing_kind": None,
            "slice_index": 0,
            "completed": True,
            "clamped": False,
            "next_page": None,
            "attempt": 0,
            "deactivated": 0,
            "snapshot": 0,
            "delta": resultado.get("delta", {}),
        }

    listing_kind = normalize_kind(payload.get("listing_kind"))
    market = str(payload.get("market") or "maceio")
    start_page = int(payload.get("start_page") or 1)
    slice_index = int(payload.get("slice_index") or 0)
    attempt = int(payload.get("attempt") or 0)
    smoke = bool(payload.get("smoke"))
    skip_deactivate = bool(payload.get("skip_deactivate")) or smoke
    run_started_at = parse_run_started_at(payload.get("run_started_at"))
    fanned_out = bool(payload.get("fanned_out"))
    # Faixa explícita: fatia filha de uma faixa que a OLX clampou.
    faixa_min = payload.get("price_min")
    faixa_max = payload.get("price_max")
    price_min = int(faixa_min) if faixa_min is not None else None
    price_max = int(faixa_max) if faixa_max is not None else None
    # Smoke CI: 2 páginas. Não mutar SCRAPER_MAX_PAGES na Lambda (isso
    # derruba a cadeia diária e o self-invoke seguinte vira full scrape).
    max_pages = 2 if smoke else None

    # Fan-out das fatias paralelas: só na fatia 0 de um kind novo
    # (slice_index=0, attempt=0, start_page=1, run_started_at presente ou None).
    is_first_slice_of_kind = (
        slice_index == 0 and attempt == 0 and start_page == 1 and not smoke
    )

    result = await job_collect_chunk(
        listing_kind=listing_kind,
        market=market,
        start_page=start_page,
        slice_index=slice_index,
        attempt=attempt,
        skip_deactivate=skip_deactivate,
        run_started_at=run_started_at,
        get_remaining_ms=get_remaining_ms,
        max_pages=max_pages,
        price_min=price_min,
        price_max=price_max,
    )

    # Propaga fanned_out do payload para o result, para que a cadeia saiba
    # que esta execução veio de um fan-out e não deve avançar entre fatias.
    if fanned_out:
        result["fanned_out"] = True

    # Dispara fan-out APÓS a fatia 0 completar seu primeiro chunk (ou clamp/erro)
    # para não atrasar o fan-out se a fatia 0 for longa.
    if is_first_slice_of_kind and result.get("success"):
        # run_started_at pode ser datetime; _fan_out_slices espera str | None
        rs_at = run_started_at.isoformat() if run_started_at is not None else None
        _fan_out_slices(
            market=market,
            listing_kind=listing_kind,
            run_started_at=rs_at,
            skip_deactivate=skip_deactivate,
            current_slice=slice_index,
        )
        # Marca a chain principal como fanned-out para que as próximas
        # auto-invocações parem ao final da fatia 0 (as demais fatias já
        # foram disparadas em paralelo e seguem suas próprias cadeias).
        result["fanned_out"] = True

    # Fatia clampada: a OLX não passa da página 100, então a faixa foi repartida
    # em duas filhas (`dividir_em`). Cada filha roda a própria cadeia, com o
    # mesmo watermark do run — é assim que a cobertura deixa de depender de
    # página funda: quando a faixa é grande demais, ela vira duas menores.
    filhas = result.get("dividir_em") or []
    if filhas and not smoke:
        rs_at = run_started_at.isoformat() if run_started_at is not None else None
        for filha in filhas:
            _self_invoke(
                _cursor(
                    market=market,
                    listing_kind=listing_kind,
                    slice_index=int(filha["slice_index"]),
                    start_page=1,
                    attempt=0,
                    run_started_at=rs_at,
                    skip_deactivate=False,
                    price_min=filha.get("price_min"),
                    price_max=filha.get("price_max"),
                )
            )

    snapshot = 0
    if smoke:
        # Smoke CI é uma invocação isolada: não encadeia nem publica.
        pass
    elif result.get("success"):
        nxt = _next_payload_after_chunk(result)
        if nxt is not None:
            # Fresh watermark when starting venda after aluguel
            if nxt.get("run_started_at") is None:
                from datetime import UTC, datetime

                nxt["run_started_at"] = datetime.now(UTC).isoformat()
            _self_invoke(nxt)
        elif _should_publish_snapshot(result):
            try:
                publish_market_snapshot()
                snapshot = 1
            except Exception:
                logger.exception("Falha ao gravar market_snapshot")
    else:
        # Chunk quebrado: repete a fatia ou segue a cadeia sem inativar.
        # Sem isto, qualquer erro encerrava a coleta (foi assim que a última
        # fatia do Recife venda morreu num deadlock e Natal ficou sem visita).
        nxt = _next_payload_after_failure(result)
        if nxt is not None:
            if nxt.get("run_started_at") is None:
                from datetime import UTC, datetime

                nxt["run_started_at"] = datetime.now(UTC).isoformat()
            _self_invoke(nxt)

    return {
        "success": result.get("success", 0),
        "count": result.get("count", 0),
        "market": result.get("market", market),
        "listing_kind": result.get("listing_kind"),
        "slice_index": result.get("slice_index", slice_index),
        "completed": result.get("completed", False),
        "clamped": result.get("clamped", False),
        "next_page": result.get("next_page"),
        "attempt": result.get("attempt", 0),
        "deactivated": result.get("deactivated", 0),
        "snapshot": snapshot,
    }


def lambda_handler(event: dict | None, context: object | None = None) -> dict[str, Any]:
    """Handler AWS Lambda (EventBridge cron, self-invoke ou GET /market-stats)."""
    if _is_market_stats_request(event):
        from stats.public import market_stats_http_response

        return market_stats_http_response()

    def get_remaining_ms() -> int | None:
        if context is None:
            return None
        getter = getattr(context, "get_remaining_time_in_millis", None)
        if getter is None:
            return None
        return int(getter())

    try:
        return asyncio.run(run(event, get_remaining_ms=get_remaining_ms))
    except Exception:
        logger.exception("Lambda collection failed")
        return {"success": 0, "count": 0}
