from __future__ import annotations

import re
from typing import Any


def parse_price(price_str: str | None) -> int | None:
    if not price_str:
        return None
    digits = re.sub(r"[^\d]", "", str(price_str))
    if not digits:
        return None
    try:
        return int(digits) * 100
    except ValueError:
        return None


def parse_size(size_str: str | None) -> int | None:
    if not size_str:
        return None
    digits = re.sub(r"[^\d]", "", str(size_str))
    if not digits:
        return None
    try:
        return int(digits)
    except ValueError:
        return None


def extract_property(properties: list[dict[str, Any]] | None, name: str) -> str | None:
    if not properties:
        return None
    for prop in properties:
        if not isinstance(prop, dict):
            continue
        if prop.get("name") == name:
            value = prop.get("value")
            if value is None:
                return None
            return str(value)
    return None


def _to_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return None


def _extract_images(raw_images: Any) -> list[dict[str, Any]]:
    if not isinstance(raw_images, list):
        return []
    out: list[dict[str, Any]] = []
    for idx, img in enumerate(raw_images):
        if not isinstance(img, dict):
            continue
        url = img.get("original")
        if not url:
            continue
        out.append(
            {
                "url": str(url),
                "url_webp": img.get("originalWebp"),
                "position": idx,
            }
        )
    return out


def parse_listing(raw: dict[str, Any]) -> dict[str, Any]:
    properties = raw.get("properties")
    if not isinstance(properties, list):
        properties = []
    location_details = raw.get("locationDetails")
    if not isinstance(location_details, dict):
        location_details = {}

    list_id = _to_int(raw.get("listId"))
    if list_id is None:
        list_id = _to_int(raw.get("olx_id"))
    if list_id is None:
        raise ValueError("listId/olx_id invalido no anuncio bruto")

    size_str = extract_property(properties, "size")
    rooms_str = extract_property(properties, "rooms")
    bathrooms_str = extract_property(properties, "bathrooms")
    garage_str = extract_property(properties, "garage_spaces")

    price_value = raw.get("priceValue")
    if price_value is None:
        price_value = raw.get("price")
    if isinstance(price_value, (int, float)):
        current_price = int(price_value) * 100
    else:
        current_price = parse_price(str(price_value) if price_value is not None else None)

    parsed = {
        "list_id": list_id,
        "url": raw.get("friendlyUrl") or raw.get("url"),
        "title": raw.get("subject") or raw.get("title"),
        "orig_list_time": _to_int(raw.get("origListTime")) or _to_int(raw.get("published_at")),
        "location": raw.get("location") or raw.get("neighborhood"),
        "municipality": location_details.get("municipality"),
        "neighbourhood": location_details.get("neighbourhood") or raw.get("neighborhood"),
        "uf": location_details.get("uf"),
        "ddd": location_details.get("ddd"),
        "current_price": current_price,
        "real_estate_type": extract_property(properties, "real_estate_type"),
        "size_m2": parse_size(size_str),
        "rooms": _to_int(rooms_str),
        "bathrooms": _to_int(bathrooms_str),
        "garage_spaces": _to_int(garage_str),
        "re_complex_features": extract_property(properties, "re_complex_features"),
        "re_type": extract_property(properties, "re_types"),
        "category_id": _to_int(raw.get("listingCategoryId")),
        "category_name": raw.get("categoryName") or raw.get("category"),
        "is_professional": bool(raw.get("professionalAd")),
        "images": _extract_images(raw.get("images")),
    }
    if not parsed["images"] and raw.get("thumbnail"):
        parsed["images"] = [{"url": str(raw["thumbnail"]), "url_webp": None, "position": 0}]
    return parsed
