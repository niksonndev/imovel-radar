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
      "run_started_at": "<iso8601>"
    }

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
        import boto3
    except ImportError:
        logger.exception("boto3 indisponível — skip self-invoke")
        return

    client = boto3.client("lambda")
    client.invoke(
        FunctionName=function_name,
        InvocationType="Event",
        Payload=json.dumps(payload).encode("utf-8"),
    )
    logger.info("Self-invoke enfileirado: %s", payload)


def _cursor(
    *,
    market: str,
    listing_kind: str,
    slice_index: int,
    start_page: int,
    attempt: int,
    run_started_at: str | None,
    skip_deactivate: bool,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "market": market,
        "listing_kind": listing_kind,
        "slice_index": slice_index,
        "start_page": start_page,
        "attempt": attempt,
        "run_started_at": run_started_at,
    }
    if skip_deactivate:
        payload["skip_deactivate"] = True
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


def _next_payload_after_chunk(result: dict[str, Any]) -> dict[str, Any] | None:
    """Próximo cursor: mais páginas, próxima fatia, venda, ou a próxima cidade.

    A watermark (``run_started_at``) não muda entre fatias do mesmo kind.
    Zera ao abrir a venda ou outra cidade, para o deactivate não misturar coletas.
    Um clamp da OLX encerra a fatia sem ``completed`` e impede o deactivate
    daquele kind; a cadeia segue para a próxima fatia ou cidade.
    """
    kind = result["listing_kind"]
    market = str(result.get("market") or "maceio")
    run_started_at = result["run_started_at"]
    slice_index = int(result.get("slice_index") or 0)
    attempt = int(result.get("attempt") or 0)
    skip_deactivate = bool(result.get("skip_deactivate"))
    clamped = bool(result.get("clamped"))

    if not result.get("completed") and result.get("next_page") and not clamped:
        return _cursor(
            market=market,
            listing_kind=kind,
            slice_index=slice_index,
            start_page=int(result["next_page"]),
            attempt=attempt,
            run_started_at=run_started_at,
            skip_deactivate=skip_deactivate,
        )

    slice_finished = bool(result.get("completed")) or clamped
    if not slice_finished:
        return None

    if clamped:
        skip_deactivate = True

    next_slice = slice_index + 1
    if next_slice < len(slices_for_kind(kind, market)):
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
    listing_kind = normalize_kind(payload.get("listing_kind"))
    market = str(payload.get("market") or "maceio")
    start_page = int(payload.get("start_page") or 1)
    slice_index = int(payload.get("slice_index") or 0)
    attempt = int(payload.get("attempt") or 0)
    skip_deactivate = bool(payload.get("skip_deactivate"))
    run_started_at = parse_run_started_at(payload.get("run_started_at"))

    result = await job_collect_chunk(
        listing_kind=listing_kind,
        market=market,
        start_page=start_page,
        slice_index=slice_index,
        attempt=attempt,
        skip_deactivate=skip_deactivate,
        run_started_at=run_started_at,
        get_remaining_ms=get_remaining_ms,
    )

    snapshot = 0
    if result.get("success"):
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
