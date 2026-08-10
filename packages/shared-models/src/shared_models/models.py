"""Schemas Pydantic compartilhados entre scraper e bot — mapeiam os registros do
SQLite (listings, alerts, users) para objetos Python tipados.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


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


class Listing(BaseModel):
    """Listing com campos JSON (images, properties) já convertidos para Python."""

    listing_id: int
    url: str
    title: str
    price_value: int | None = None
    old_price: int | None = None
    municipality: str
    neighbourhood: str
    category: str
    images: list[str]
    properties: Properties
    active: bool = True


class Alert(BaseModel):
    """Alerta salvo no banco."""

    id: int
    chat_id: int
    alert_name: str | None = None
    min_price: int | None = None
    max_price: int | None = None
    neighbourhoods: list[str] | None = None
    active: bool = True
    created_at: datetime
