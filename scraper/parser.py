"""
Normaliza um dict bruto de anúncio da OLX (ex.: nó em __NEXT_DATA__) para um
formato fixo com apenas: listId, url, title, priceValue, oldPrice, municipality,
neighbourhood, properties, category, images.
"""
from __future__ import annotations

import json
import re
from typing import Any

from utils.models import Listing
from utils.pricing import money_to_int

__all__ = ["normalize_olx_listing"]


def _normalize_property_value(name: str, value: Any) -> Any:
    if name in {"condominio", "iptu"}:
        return money_to_int(value)
    if name == "size":
        match = re.search(r"\d+", str(value))
        return int(match.group(0)) if match else None
    if name in {"rooms", "bathrooms", "garage_spaces"}:
        return int(value) if str(value).isdigit() else None
    return value


def normalize_olx_listing(raw: dict[str, Any]) -> Listing:
    title_raw = raw.get("title") or raw.get("subject") or ""
    title = str(title_raw)[:500] if title_raw else ""
    location = raw["locationDetails"]

    properties_list = [
        {name: _normalize_property_value(name.lower(), prop["value"])}
        for prop in raw["properties"]
        if isinstance(prop, dict)
        and (name := str(prop.get("name") or "").strip())
        and "value" in prop
    ]

    images_list = [
        img["originalWebp"]
        for img in raw["images"]
        if isinstance(img, dict) and "originalWebp" in img
    ]

    return {
        "listId": int(raw["listId"]),
        "url": str(raw.get("friendlyUrl") or raw.get("url") or ""),
        "title": title,
        "priceValue": money_to_int(raw.get("priceValue") or raw.get("price")),
        "oldPrice": money_to_int(raw.get("oldPrice")),
        "municipality": str(location.get("municipality") or ""),
        "neighbourhood": str(location.get("neighbourhood") or ""),
        "properties": json.dumps(properties_list, ensure_ascii=False),
        "category": str(raw.get("category") or raw.get("categoryName") or ""),
        "images": json.dumps(images_list, ensure_ascii=False),
    }
