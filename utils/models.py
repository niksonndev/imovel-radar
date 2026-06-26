from __future__ import annotations
from typing import TypedDict


class Listing(TypedDict):
    listId: int
    url: str
    title: str
    priceValue: int | None
    oldPrice: int | None
    municipality: str
    neighbourhood: str | None
    category: str
    images: str
    properties: str


class Alert(TypedDict):
    id: int
    user_id: int
    alert_name: str
    min_price: int
    max_price: int
    neighbourhoods: str | None  # JSON array, deserializar quando usar
    active: bool
    created_at: str
