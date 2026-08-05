"""Cliente HTTP tipado para a API do scraper.

Usa ``httpx.AsyncClient`` com timeout configurável.
Todos os métodos retornam os modelos Pydantic definidos em ``shared_models``.
"""

from __future__ import annotations

import logging

from shared_models.api_schemas import (
    AlertsListResponse,
    CreateAlertRequest,
    CreateAlertResponse,
    ListingsListHydratedResponse,
    MarkNotifiedRequest,
    MatchesResponse,
    NeighbourhoodsResponse,
)

import config

logger = logging.getLogger(__name__)


class ScraperAPI:
    """Cliente HTTP para a API do scraper."""

    def __init__(self, base_url: str | None = None) -> None:
        import httpx

        self._base_url = (base_url or config.SCRAPER_API_URL).rstrip("/")
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            timeout=httpx.Timeout(30.0),
        )

    async def close(self) -> None:
        await self._client.aclose()

    # ── Listings ──────────────────────────────────────────────────────────

    async def get_listings(self, ids: list[int] | None = None) -> ListingsListHydratedResponse:
        """Retorna listings. Filtra por IDs se fornecido."""
        params = {}
        if ids:
            params["ids"] = ",".join(str(i) for i in ids)
        r = await self._client.get("/listings", params=params)
        r.raise_for_status()
        return ListingsListHydratedResponse(**r.json())

    async def get_listing(self, list_id: int) -> ListingsListHydratedResponse:
        """Retorna um listing específico."""
        r = await self._client.get(f"/listings/{list_id}")
        r.raise_for_status()
        # Retorna como resposta de lista com 1 item para compatibilidade
        listing_data = r.json()
        return ListingsListHydratedResponse(listings=[listing_data], total=1)

    # ── Neighbourhoods ────────────────────────────────────────────────────

    async def get_neighbourhoods(self) -> NeighbourhoodsResponse:
        """Retorna lista de bairros disponíveis."""
        r = await self._client.get("/listings/neighbourhoods")
        r.raise_for_status()
        return NeighbourhoodsResponse(**r.json())

    # ── Alerts ────────────────────────────────────────────────────────────

    async def create_alert(self, req: CreateAlertRequest) -> CreateAlertResponse:
        """Cria um novo alerta."""
        r = await self._client.post("/alerts", json=req.model_dump())
        r.raise_for_status()
        return CreateAlertResponse(**r.json())

    async def list_alerts(self, user_id: int) -> AlertsListResponse:
        """Lista alertas de um usuário."""
        r = await self._client.get("/alerts", params={"user_id": user_id})
        r.raise_for_status()
        return AlertsListResponse(**r.json())

    async def get_alert(self, alert_id: int) -> AlertsListResponse:
        """Retorna detalhe de um alerta."""
        r = await self._client.get(f"/alerts/{alert_id}")
        r.raise_for_status()
        return AlertsListResponse(**r.json())

    async def delete_alert(self, alert_id: int, user_id: int) -> dict:
        """Remove um alerta."""
        r = await self._client.delete(f"/alerts/{alert_id}", params={"user_id": user_id})
        r.raise_for_status()
        return r.json()

    # ── Matches ───────────────────────────────────────────────────────────

    async def get_matches(self, alert_id: int) -> MatchesResponse:
        """Retorna matches não notificados para um alerta."""
        r = await self._client.get(f"/alerts/{alert_id}/matches")
        r.raise_for_status()
        return MatchesResponse(**r.json())

    async def mark_notified(self, alert_id: int, listing_ids: list[int]) -> dict:
        """Marca listings como notificados para um alerta."""
        req = MarkNotifiedRequest(listing_ids=listing_ids)
        r = await self._client.post(
            f"/alerts/{alert_id}/matches/notify",
            json=req.model_dump(),
        )
        r.raise_for_status()
        return r.json()

    # ── Active alerts (polling) ───────────────────────────────────────────

    async def get_active_alerts(self) -> AlertsListResponse:
        """Retorna todos os alertas ativos."""
        r = await self._client.get("/alerts/active")
        r.raise_for_status()
        return AlertsListResponse(**r.json())
