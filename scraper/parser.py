"""
Normaliza um dict bruto de anúncio da OLX (ex.: nó em __NEXT_DATA__) para um
formato fixo com apenas: listId, url, title, priceValue, oldPrice, municipality,
neighbourhood, properties, category, images.
"""
from __future__ import annotations

import json
import re
from typing import Any

__all__ = ["normalize_olx_listing", "price_value_to_float"]

_URL_ID_RE = re.compile(r"/(\d{8,})(?:\?|$|/)", re.I)

def _parse_first_int(value: Any) -> int | None:
    """
    Extrai o primeiro inteiro de uma string (ex.: '2', '2 qtos', '1 vaga').

    Usado para normalizar: `rooms`, `bathrooms`, `garage_spaces`.
    """
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)

    s = str(value).strip()
    # Tenta ser tolerante com variações de formatação vindas do OLX.
    m = re.search(r"\d+", s)
    if not m:
        return None
    try:
        return int(m.group(0))
    except ValueError:
        return None


def _parse_size_m2_to_int(value: Any) -> int | None:
    """
    Converte área em m² vindas como string:
    - '40m²' / '40 m2'
    - '40,5 m2'

    Retorna apenas o valor inteiro (ex.: '40,5 m2' -> 40).
    """
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)

    s = str(value).strip().lower()
    # Mantém apenas o primeiro número encontrado (com decimal opcional).
    m = re.search(r"(\d+(?:[.,]\d+)?)", s)
    if not m:
        return None

    num = m.group(1)
    # Caso tenha separadores de milhar e decimal, tratamos o último como decimal.
    if "," in num and "." in num:
        num = num.replace(".", "").replace(",", ".")
    elif "," in num and "." not in num:
        num = num.replace(",", ".")

    try:
        # Requisito do usuário: manter apenas o valor inteiro.
        # int(float(...)) trunca em vez de arredondar.
        return int(float(num))
    except ValueError:
        return None


def money_to_cents(value: Any) -> int | None:
    """
    Converte valores monetários do OLX para centavos (int).

    Exemplos:
    - 'R$ 2.700' -> 270000
    - 'R$ 1.234,56' -> 123456
    """
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
    """
    Converte `priceValue` (string ou centavos int) para float em reais.

    Mantém a mesma convenção do restante do pipeline: centavos -> /100.
    """
    cents = money_to_cents(value)
    if cents is None:
        return None
    return cents / 100


def normalize_olx_listing(raw: dict) -> dict[str, Any]:
    """
    Normaliza um dict bruto de anúncio da OLX para um formato estável.

    `properties` e `images` são devolvidos como JSON string.
    Além disso, converte:
    - `size` ('40m²') -> inteiro (40)
    - `rooms`/`bathrooms`/`garage_spaces` -> INTEGER
    """
    # 1) listId (preferência: listId/adId; fallback: url/friendlyUrl)
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

    # 2) URL e título
    url = raw.get("url") or raw.get("friendlyUrl") or ""
    if isinstance(url, str):
        if url and not url.startswith("http"):
            url = "https://www.olx.com.br" + url
    else:
        url = ""

    title_raw = raw.get("title") or raw.get("subject") or ""
    title = str(title_raw)[:500] if title_raw else ""

    # 3) preços em centavos (int)
    price_value = raw.get("priceValue")
    if price_value is None and raw.get("price") is not None:
        price_value = raw.get("price")
    price_value = money_to_cents(price_value)

    old_price = raw.get("oldPrice")
    old_price = money_to_cents(old_price)

    # 4) localização (strings)
    loc = raw.get("locationDetails") or {}
    municipality, neighbourhood = "", ""
    if isinstance(loc, dict):
        municipality = str(loc.get("municipality") or "")
        neighbourhood = str(loc.get("neighbourhood") or "")

    # 5) properties: lista normalizada -> JSON string
    props = raw.get("properties")
    properties_list: list[dict[str, Any]] = []
    if isinstance(props, list):
        for p in props:
            if not isinstance(p, dict) or "name" not in p or "value" not in p:
                continue

            name = p["name"]
            value = p["value"]
            name_norm = str(name).strip()
            name_l = name_norm.lower()

            if name_l in {"condominio", "iptu"}:
                normalized_value = money_to_cents(value)
            elif name_l == "size":
                normalized_value = _parse_size_m2_to_int(value)
            elif name_l in {"rooms", "bathrooms", "garage_spaces"}:
                normalized_value = _parse_first_int(value)
            else:
                normalized_value = value

            properties_list.append({name_norm: normalized_value})

    # O resto do pipeline espera string JSON aqui.
    properties = json.dumps(properties_list, ensure_ascii=False)

    cat_raw = raw.get("category") or raw.get("categoryName") or ""
    category = str(cat_raw) if cat_raw else ""

    # 6) images: lista -> JSON string
    imgs = raw.get("images")
    images_list = (
        [img["originalWebp"] for img in imgs if isinstance(img, dict) and "originalWebp" in img]
        if isinstance(imgs, list)
        else []
    )
    # O resto do pipeline espera string JSON aqui.
    images = json.dumps(images_list, ensure_ascii=False)

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
