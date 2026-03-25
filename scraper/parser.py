"""
Normaliza um dict bruto de anúncio da OLX (ex.: nó em __NEXT_DATA__) para um
formato fixo com apenas: listId, url, title, priceValue, oldPrice, municipality,
neighbourhood, properties, category, images.
"""
from __future__ import annotations

import re
from typing import Any

__all__ = ["normalize_olx_listing", "price_value_to_float"]

_URL_ID_RE = re.compile(r"/(\d{8,})(?:\?|$|/)", re.I)


def money_to_cents(value: Any) -> int | None:
    """Converte valores monetários (ex.: 'R$ 2.700'/'R$ 1.234,56') para centavos (int)."""
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        # Assumimos que int já vem em centavos (convenção do parser normalizado).
        return value
    if isinstance(value, float):
        # Assumimos que float já está em reais.
        return int(round(value * 100))

    s = str(value).strip()
    if not s:
        return None

    negative = s.startswith("-")
    s = s.replace("R$", "").replace("r$", "").strip()
    s = s.replace(" ", "")
    # Mantém apenas caracteres relevantes para parsing (dígitos, '.' e ',').
    s = re.sub(r"[^\d.,-]", "", s)
    if not s or s == "-":
        return None

    # Formato OLX pt-BR: milhares em '.' e decimais em ','.
    # Mas alguns casos podem vir com '.' como decimal (sem vírgula).
    if "," in s:
        s = s.replace(".", "")
        integer_part, dec_part = s.split(",", 1)
    elif "." in s:
        parts = s.split(".")
        last = parts[-1]
        # Se a última seção tiver 1-2 dígitos, tratamos como decimal; caso contrário, como milhares.
        if 1 <= len(last) <= 2:
            integer_part = "".join(parts[:-1])
            dec_part = last
        else:
            integer_part = "".join(parts)
            dec_part = ""
    else:
        integer_part = s
        dec_part = ""

    integer_digits = re.sub(r"[^\d]", "", integer_part)
    if not integer_digits:
        return None

    dec_digits = re.sub(r"[^\d]", "", dec_part)
    if not dec_digits:
        cents = int(integer_digits) * 100
    else:
        # Garante 2 dígitos (ex.: '5' => '50', '56' => '56').
        cents = int(integer_digits) * 100 + int((dec_digits + "00")[:2])

    return -cents if negative else cents


def price_value_to_float(value: Any) -> float | None:
    """Converte priceValue (string ou centavos int) em float (reais) para comparações/exibição."""
    cents = money_to_cents(value)
    if cents is None:
        return None
    return cents / 100


def normalize_olx_listing(raw: dict) -> dict[str, Any]:
    """
    Mapeia *raw* (como em debug_ad.json) para dict enxuto só com as chaves
    esperadas; demais campos são descartados.
    """
    lid: int | None = None
    for key in ("listId", "adId"):
        v = raw.get(key)
        if v is None or isinstance(v, bool):
            continue
        if isinstance(v, float) and v.is_integer():
            lid = int(v)
            break
        if isinstance(v, int):
            lid = v
            break
        if isinstance(v, str) and v.isdigit() and len(v) >= 6:
            lid = int(v)
            break

    if lid is None:
        for ukey in ("url", "friendlyUrl"):
            u = raw.get(ukey)
            if isinstance(u, str):
                m = _URL_ID_RE.search(u)
                if m:
                    lid = int(m.group(1))
                    break

    url = raw.get("url") or raw.get("friendlyUrl") or ""
    if isinstance(url, str):
        if url and not url.startswith("http"):
            url = "https://www.olx.com.br" + url
    else:
        url = ""

    title_raw = raw.get("title") or raw.get("subject") or ""
    title = str(title_raw)[:500] if title_raw else ""

    price_value = raw.get("priceValue")
    if price_value is None and raw.get("price") is not None:
        price_value = raw.get("price")
    price_value = money_to_cents(price_value)

    old_price = raw.get("oldPrice")
    old_price = money_to_cents(old_price)

    loc = raw.get("locationDetails") or {}
    municipality, neighbourhood = "", ""
    if isinstance(loc, dict):
        municipality = str(loc.get("municipality") or "")
        neighbourhood = str(loc.get("neighbourhood") or "")

    props = raw.get("properties")
    properties = (
        [
            {
                p["name"]: (
                    money_to_cents(p["value"])
                    if str(p["name"]).strip().lower() in {"condominio", "iptu"}
                    else p["value"]
                )
            }
            for p in props
            if isinstance(p, dict) and "name" in p and "value" in p
        ]
        if isinstance(props, list) else []
    )

    cat_raw = raw.get("category") or raw.get("categoryName") or ""
    category = str(cat_raw) if cat_raw else ""

    imgs = raw.get("images")
    images = (
        [img["originalWebp"] for img in imgs if isinstance(img, dict) and "originalWebp" in img]
        if isinstance(imgs, list) else []
    )

    return {
        "listId": lid,
        "url": url,
        "title": title,
        "priceValue": price_value,
        "oldPrice": old_price,
        "municipality": municipality,
        "neighbourhood": neighbourhood,
        "properties": properties,
        "category": category,
        "images": images,
    }
