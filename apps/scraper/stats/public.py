"""Resposta HTTP do snapshot mais recente (API Gateway payload 2.0)."""

from __future__ import annotations

import json
import logging
from typing import Any

from sqlmodel import Session

from database import engine
from stats.aggregate import latest_market_snapshot

logger = logging.getLogger(__name__)


def _response(status: int, body: dict[str, Any], *, max_age: int) -> dict[str, Any]:
    return {
        "statusCode": status,
        "headers": {
            "content-type": "application/json; charset=utf-8",
            "cache-control": f"public, max-age={max_age}",
        },
        "body": json.dumps(body, ensure_ascii=False),
    }


def market_stats_http_response() -> dict[str, Any]:
    try:
        with Session(engine) as session:
            payload = latest_market_snapshot(session)
    except Exception:
        logger.exception("Falha ao ler market_snapshot")
        return _response(503, {"detail": "indisponível"}, max_age=60)
    if payload is None:
        return _response(404, {"detail": "snapshot indisponível"}, max_age=60)
    return _response(200, payload, max_age=3600)
