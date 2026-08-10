"""Schemas de request/response para a API HTTP do scraper.

Todos os modelos usam ``extra="forbid"`` para rejeitar campos desconhecidos.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, model_validator

from .models import Alert, Listing

# ── Listings ─────────────────────────────────────────────────────────────


class UnnotifiedListing(Listing):
    model_config = ConfigDict(extra="forbid")

    alert_id: int


class UnnotifiedListingsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    listings: list[UnnotifiedListing]
    total: int


# ── Alerts ───────────────────────────────────────────────────────────────


class CreateAlertRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chat_id: int
    alert_name: str
    min_price: int | None = None
    max_price: int | None = None
    neighbourhoods: list[str]

    @model_validator(mode="after")
    def check_price_range(self) -> "CreateAlertRequest":
        if self.min_price is None and self.max_price is None:
            raise ValueError("Informe min_price, max_price, ou ambos.")
        return self


class CreateAlertResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    message: str = "Alerta criado com sucesso"


class UserResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chat_id: int
    created_at: datetime | None = None


class AlertsListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    alerts: list[Alert]
    total: int


# ── Matches ──────────────────────────────────────────────────────────────

class NotifiedPair(BaseModel):
    model_config = ConfigDict(extra="forbid")

    alert_id: int
    listing_id: int



class MatchesResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    alert_id: int
    matches: list[Listing]
    total: int


class MarkNotifiedRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pairs: list[NotifiedPair]
