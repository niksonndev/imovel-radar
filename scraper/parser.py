"""
PARSER = HTML → dados estruturados (dict/list).

O site OLX usa Next.js: muitos dados vêm num <script id="__NEXT_DATA__"> em JSON gigante.
_walk_find_ads percorre esse JSON (dict/list aninhados) e acha objetos que parecem anúncio.
Se não achar o suficiente, fallback: links <a href="/d/..."> no HTML.
"""
from __future__ import annotations

import json
import logging
import pprint
import re
from typing import Any

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

OLX_ID_RE = re.compile(r"/(\d{8,})(?:\?|$|/)", re.I)


def _normalize_url(href: str) -> str:
    if href.startswith("http"):
        return href.split("?")[0].rstrip("/")
    return "https://www.olx.com.br" + href.split("?")[0].rstrip("/")


def _parse_price(val: Any) -> float | None:
    """Tira só os dígitos de strings tipo 'R$ 320.000' → 320000.0"""
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val)
    digits = re.sub(r"[^\d]", "", s)
    if not digits:
        return None
    try:
        return float(digits)
    except ValueError:
        return None


def _walk_first_raw_ad(obj: Any, depth: int = 0) -> dict | None:
    """Primeiro dict na árvore JSON com chave listId ou adId (debug)."""
    if depth > 25 or obj is None:
        return None
    if isinstance(obj, dict):
        if "listId" in obj or "adId" in obj:
            return obj
        for v in obj.values():
            found = _walk_first_raw_ad(v, depth + 1)
            if found is not None:
                return found
    elif isinstance(obj, list):
        for item in obj:
            found = _walk_first_raw_ad(item, depth + 1)
            if found is not None:
                return found
    return None


def dump_sample_ad(html: str) -> None:
    """
    Extrai __NEXT_DATA__, acha o primeiro objeto com listId ou adId e imprime o dict inteiro.
    """
    soup = BeautifulSoup(html, "lxml")
    script = soup.find("script", id="__NEXT_DATA__")
    if not script or not script.string:
        print("dump_sample_ad: sem __NEXT_DATA__ no HTML")
        return
    try:
        data = json.loads(script.string)
    except json.JSONDecodeError as e:
        print(f"dump_sample_ad: JSON inválido: {e}")
        return
    raw = _walk_first_raw_ad(data)
    if raw is None:
        print("dump_sample_ad: nenhum objeto com listId/adId encontrado")
        return
    pprint.pprint(raw, width=120, sort_dicts=False, compact=False)


def _walk_find_ads(obj: Any, out: list[dict], depth: int = 0) -> None:
    """
    Recursão em dict/list. depth limit evita loop infinito se JSON circular (não deveria).
    Quando encontra listId/adId ou URL com ID, monta um dict padronizado e append em out.
    """
    if depth > 25 or obj is None:
        return
    if isinstance(obj, dict):
        lid = str(obj.get("listId") or obj.get("adId") or "")
        if not lid.isdigit() or len(lid) < 6:
            if isinstance(obj.get("url"), str) and "/d/" in obj["url"]:
                m = OLX_ID_RE.search(obj["url"])
                lid = m.group(1) if m else ""
        if lid.isdigit() and len(lid) >= 6:
            title = obj.get("title") or obj.get("subject") or ""
            price = _parse_price(obj.get("priceValue"))
            if price is None and isinstance(obj.get("price"), (int, float)):
                price = float(obj["price"])
            if price is None and isinstance(obj.get("price"), dict):
                price = _parse_price(obj["price"].get("value"))
            url = obj.get("url") or obj.get("friendlyUrl")
            if url and not url.startswith("http"):
                url = "https://www.olx.com.br" + url
            images = obj.get("images") or obj.get("image") or []
            thumb = None
            if isinstance(images, list) and images:
                first = images[0]
                thumb = first if isinstance(first, str) else first.get("url") or first.get("original")
            elif isinstance(images, dict):
                thumb = images.get("url") or images.get("original")
            loc_details = obj.get("locationDetails") or {}
            neighborhood = ""
            if isinstance(loc_details, dict):
                neighborhood = loc_details.get("neighbourhood") or ""
            props = obj.get("properties") or []
            bedrooms = None
            area_m2 = None
            bathrooms = None
            garage_spaces = None
            if isinstance(props, list):
                for p in props:
                    if not isinstance(p, dict):
                        continue
                    name = (p.get("name") or "").lower()
                    val = p.get("value")
                    if "quarto" in name or name in ("bedrooms", "rooms"):
                        try:
                            bedrooms = int(re.sub(r"\D", "", str(val)) or 0)
                        except ValueError:
                            pass
                    if name == "bathrooms":
                        try:
                            bathrooms = int(re.sub(r"\D", "", str(val)) or 0)
                        except ValueError:
                            pass
                    if name == "garage_spaces":
                        try:
                            garage_spaces = int(re.sub(r"\D", "", str(val)) or 0)
                        except ValueError:
                            pass
                    if "m²" in str(val) or "area" in name or "área" in name or name == "size":
                        try:
                            area_m2 = float(re.sub(r"[^\d.,]", "", str(val)).replace(",", "."))
                        except ValueError:
                            pass
            category = str(obj.get("categoryName") or obj.get("category") or "")
            old_price = _parse_price(obj.get("oldPrice"))
            pub_raw = obj.get("origListTime")
            if pub_raw is None:
                pub_raw = obj.get("date")
            if isinstance(pub_raw, (int, float)):
                published_at = int(pub_raw)
            else:
                published_at = None
            is_professional = bool(obj.get("professionalAd"))
            feat = obj.get("featured")
            is_featured = isinstance(feat, list) and len(feat) > 0
            out.append(
                {
                    "olx_id": lid,
                    "title": str(title)[:500],
                    "price": price,
                    "url": url or f"https://www.olx.com.br/d/oferta-{lid}",
                    "thumbnail": thumb,
                    "neighborhood": str(neighborhood),
                    "bedrooms": bedrooms,
                    "area_m2": area_m2,
                    "category": category,
                    "old_price": old_price,
                    "published_at": published_at,
                    "is_professional": is_professional,
                    "is_featured": is_featured,
                    "bathrooms": bathrooms,
                    "garage_spaces": garage_spaces,
                }
            )
        for v in obj.values():
            _walk_find_ads(v, out, depth + 1)
    elif isinstance(obj, list):
        for item in obj:
            _walk_find_ads(item, out, depth + 1)


def parse_search_page(html: str) -> list[dict]:
    """HTML da listagem → lista de anúncios (cada um é um dict)."""
    out: list[dict] = []
    seen_ids: set[str] = set()

    soup = BeautifulSoup(html, "lxml")
    script = soup.find("script", id="__NEXT_DATA__")
    if script and script.string:
        try:
            data = json.loads(script.string)
            _walk_find_ads(data, out)
        except json.JSONDecodeError as e:
            logger.warning("__NEXT_DATA__ JSON: %s", e)

    dedup: dict[str, dict] = {}
    for ad in out:
        oid = ad.get("olx_id")
        if not oid or oid in seen_ids:
            continue
        if oid not in dedup or (ad.get("url") and "olx.com.br/d/" in str(ad.get("url"))):
            dedup[oid] = ad
        seen_ids.add(oid)
    result = list(dedup.values())

    if len(result) < 3:
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "/d/" not in href:
                continue
            m = OLX_ID_RE.search(href)
            if not m:
                continue
            oid = m.group(1)
            if oid in dedup:
                continue
            dedup[oid] = {
                "olx_id": oid,
                "title": (a.get_text() or "Anúncio")[:500],
                "price": None,
                "url": _normalize_url(href),
                "thumbnail": None,
                "neighborhood": "",
                "bedrooms": None,
                "area_m2": None,
            }
        result = list(dedup.values())

    return result


def parse_listing_page(html: str) -> dict[str, Any]:
    """Uma página de detalhe do anúncio (preço, título, se sumiu)."""
    removed = False
    lower = html.lower()
    if "não encontrado" in lower or "nao encontrado" in lower or "anúncio expirado" in lower:
        removed = True
    title = None
    price = None

    soup = BeautifulSoup(html, "lxml")
    if "404" in html[:2000] and len(html) < 15000:
        removed = True

    script = soup.find("script", id="__NEXT_DATA__")
    if script and script.string:
        try:
            data = json.loads(script.string)
            ads: list[dict] = []
            _walk_find_ads(data, ads)
            if ads:
                a = ads[0]
                title = a.get("title")
                price = a.get("price")
        except json.JSONDecodeError:
            pass

    if not title:
        h1 = soup.find("h1")
        if h1:
            title = h1.get_text(strip=True)[:500]
    if price is None:
        for el in soup.find_all(string=re.compile(r"R\$\s*[\d.]")):
            price = _parse_price(el)
            if price:
                break

    return {
        "title": title,
        "price": price,
        "removed": removed,
        "not_found": "404" in html[:3000] and "olx" in lower,
    }
