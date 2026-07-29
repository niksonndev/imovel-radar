"""Schemas de request/response para a API HTTP do scraper.

Todos os modelos usam ``extra="forbid"`` para rejeitar campos desconhecidos.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from .models import Alert, HydratedListing, Listing

# ── Listings ─────────────────────────────────────────────────────────────


class ListingsListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    listings: list[Listing]
    total: int


class ListingsByIdsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ids: list[int]


class ListingsListHydratedResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    listings: list[HydratedListing]
    total: int


# ── Alerts ───────────────────────────────────────────────────────────────


class CreateAlertRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: int
    alert_name: str
    min_price: int
    max_price: int
    neighbourhoods: str  # JSON array


class CreateAlertResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    message: str = "Alerta criado com sucesso"


class AlertsListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    alerts: list[Alert]
    total: int


# ── Matches ──────────────────────────────────────────────────────────────


class MatchesResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    alert_id: int
    matches: list[HydratedListing]
    total: int


class MarkNotifiedRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    listing_ids: list[int]


# ── Neighbourhoods ───────────────────────────────────────────────────────


class NeighbourhoodsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    neighbourhoods: list[str]


# ── Health ───────────────────────────────────────────────────────────────


class HealthResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str = "ok"
    listings_count: int = 0
    alerts_count: int = 0
