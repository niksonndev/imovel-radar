"""Schemas Pydantic compartilhados entre scraper e bot — mapeiam os registros do
SQLite (listings, alerts, users) para objetos Python tipados.

A nomenclatura preserva snake_case (padrão Python/Pydantic) — a serialização
para JSON usa ``model_dump(by_alias=True)`` quando os nomes da OLX/SQLite
diferirem (ex.: ``listId``, ``oldPrice``).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class Listing(BaseModel):
    """Um anúncio individual do OLX, normalizado após o parser."""

    list_id: int = Field(alias="listId")
    url: str
    title: str
    price_value: int | None = Field(default=None, alias="priceValue")
    old_price: int | None = Field(default=None, alias="oldPrice")
    municipality: str
    neighbourhood: str | None = None
    category: str
    images: str  # JSON serializado (lista de URLs)
    properties: str  # JSON serializado (lista de dicts)
    active: bool = True
    first_seen_at: datetime | None = None
    updated_at: datetime | None = None


class Properties(BaseModel):
    """Propriedades extraídas de um anúncio (tamanho, quartos, etc.)."""

    category: str | None = None
    real_estate_type: str | None = None  # Aluguel / Venda
    size: int | None = None
    rooms: int | None = None
    bathrooms: int | None = None
    garage_spaces: int | None = None
    condominio: int | None = None
    iptu: int | None = None
    re_features: str | None = None
    re_complex_features: str | None = None
    re_types: str | None = None


class HydratedListing(BaseModel):
    """Listing com campos JSON (images, properties) já convertidos para Python."""

    list_id: int = Field(alias="listId")
    url: str
    title: str
    price_value: int | None = Field(default=None, alias="priceValue")
    old_price: int | None = Field(default=None, alias="oldPrice")
    municipality: str
    neighbourhood: str | None = None
    category: str
    images: list[str]
    properties: list[Properties]


class Alert(BaseModel):
    """Alerta salvo no banco. ``neighbourhoods`` é JSON serializado."""

    id: int
    user_id: int  # Telegram chat_id — the user's identity
    alert_name: str | None = None
    min_price: int
    max_price: int
    neighbourhoods: str  # JSON array, deserializar quando usar
    active: bool = True
    created_at: datetime | None = None


class CreateAlertData(BaseModel):
    """Dados para criar um novo alerta. ``neighbourhoods`` já serializado como JSON."""

    user_id: int
    alert_name: str
    min_price: int
    max_price: int
    neighbourhoods: str  # JSON string