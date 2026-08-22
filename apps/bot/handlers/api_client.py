"""Cliente HTTP tipado para a API do scraper.

Usa ``httpx.AsyncClient`` com timeout configurável.
Todos os métodos retornam os modelos Pydantic definidos em ``shared_models``.
"""

from __future__ import annotations

import logging

import httpx
from shared_models.api_schemas import (
    AlertsListResponse,
    CreateAlertRequest,
    CreateAlertResponse,
    MarkNotifiedRequest,
    NotifiedPair,
    UnnotifiedListingsResponse,
    UserResponse,
)
from shared_models.models import Alert

import config

logger = logging.getLogger(__name__)

_client: httpx.AsyncClient | None = None


def init_client(base_url: str | None = None) -> None:
    """Inicializa o client HTTP module-level. Deve ser chamado uma vez no startup."""
    global _client
    resolved_base_url = (base_url or config.SCRAPER_API_URL).rstrip("/")
    _client = httpx.AsyncClient(
        base_url=resolved_base_url,
        timeout=httpx.Timeout(30.0),
    )


def _get_client() -> httpx.AsyncClient:
    if _client is None:
        raise RuntimeError("scraper_api client não inicializado. Chame init_client() primeiro.")
    return _client


async def close_client() -> None:
    if _client is not None:
        await _client.aclose()


# ── Listings ─────────────────────────────────────────────────────────────


async def get_unnotified_listings(chat_id: int) -> UnnotifiedListingsResponse:
    """Retorna listings não notificados de todos os alertas ativos do usuário."""
    res = await _get_client().get(f"/listings/{chat_id}/unnotified")
    res.raise_for_status()
    return UnnotifiedListingsResponse(**res.json())


async def mark_listings_notified(chat_id: int, pairs: list[NotifiedPair]) -> dict:
    """Marca pares (alerta, listing) como notificados."""
    req = MarkNotifiedRequest(pairs=pairs)
    res = await _get_client().post(f"/listings/{chat_id}/mark-notified", json=req.model_dump())
    res.raise_for_status()
    return res.json()


# ── Neighbourhoods ───────────────────────────────────────────────────────


async def get_neighbourhoods() -> list[str]:
    """Retorna lista de bairros disponíveis."""
    res = await _get_client().get("/listings/neighbourhoods")
    res.raise_for_status()
    return res.json()


# ── Users ────────────────────────────────────────────────────────────────


async def create_user(chat_id: int) -> UserResponse:
    """Cria um usuário para o chat informado."""
    res = await _get_client().post(f"/users/{chat_id}")
    res.raise_for_status()
    return UserResponse(**res.json())


async def get_user(chat_id: int) -> UserResponse:
    """Retorna um usuário pelo chat_id."""
    res = await _get_client().get(f"/users/{chat_id}")
    res.raise_for_status()
    return UserResponse(**res.json())


# ── Alerts ───────────────────────────────────────────────────────────────


async def create_alert(req: CreateAlertRequest) -> CreateAlertResponse:
    """Cria um novo alerta."""
    res = await _get_client().post("/alerts", json=req.model_dump())
    res.raise_for_status()
    return CreateAlertResponse(**res.json())


async def get_alert_for_user(alert_id: int, chat_id: int) -> Alert:
    """Retorna um alerta."""
    res = await _get_client().get(f"/alerts/{chat_id}/{alert_id}")
    res.raise_for_status()
    return Alert(**res.json())


async def get_alerts_for_user(chat_id: int) -> AlertsListResponse:
    """Retorna todos os alertas de um usuário."""
    res = await _get_client().get(f"/alerts/{chat_id}")
    res.raise_for_status()
    return AlertsListResponse(**res.json())


async def get_active_alerts_for_user(chat_id: int) -> AlertsListResponse:
    """Retorna todos os alertas ativos de um usuário."""
    res = await _get_client().get(f"/alerts/{chat_id}/active")
    res.raise_for_status()
    return AlertsListResponse(**res.json())


async def delete_alert(alert_id: int, chat_id: int) -> dict:
    """Remove um alerta."""
    res = await _get_client().delete(f"/alerts/{chat_id}/{alert_id}")
    res.raise_for_status()
    return res.json()
