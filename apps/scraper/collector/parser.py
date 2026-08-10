"""
Normaliza um dict bruto de anúncio da OLX (nó do array "ads" extraído do
payload RSC streaming) para um formato fixo com apenas: listing_id, url,
title, price_value, old_price, municipality, neighbourhood, properties,
category, images.
"""

from __future__ import annotations

import re
from typing import Any, TypedDict

from shared_models.utils import money_to_int

__all__ = ["RawAd", "normalize_olx_listing"]


class RawAd(TypedDict):
    """Payload bruto do anúncio coletado pelo scraper antes de persistir no banco."""

    listing_id: int
    url: str
    title: str
    price_value: int | None
    old_price: int | None
    municipality: str
    neighbourhood: str
    properties: dict[str, Any]
    category: str
    images: list[str]


def _normalize_property_value(name: str, value: Any) -> Any:
    if name in {"condominio", "iptu"}:
        return money_to_int(value)
    if name == "size":
        match = re.search(r"\d+", str(value))
        return int(match.group(0)) if match else None
    if name in {"rooms", "bathrooms", "garage_spaces"}:
        return int(value) if str(value).isdigit() else None
    return value


def normalize_olx_listing(raw: dict[str, Any]) -> RawAd:
    title_raw = raw.get("title") or raw.get("subject") or ""
    title = str(title_raw)[:500] if title_raw else ""
    location = raw["locationDetails"]

    properties_dict = {
        name: _normalize_property_value(name.lower(), prop["value"])
        for prop in raw["properties"]
        if isinstance(prop, dict)
        and (name := str(prop.get("name") or "").strip())
        and "value" in prop
    }

    images_list = [
        img["originalWebp"]
        for img in raw["images"]
        if isinstance(img, dict) and "originalWebp" in img
    ]

    return {
        "listing_id": int(raw["listId"]),
        "url": str(raw.get("friendlyUrl") or raw.get("url") or ""),
        "title": title,
        "price_value": money_to_int(raw.get("priceValue") or raw.get("price")),
        "old_price": money_to_int(raw.get("oldPrice")),
        "municipality": str(location.get("municipality") or ""),
        "neighbourhood": str(location.get("neighbourhood") or ""),
        "properties": properties_dict,
        "category": str(raw.get("category") or raw.get("categoryName") or ""),
        "images": images_list,
    }