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