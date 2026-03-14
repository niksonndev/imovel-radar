"""
PARSER = HTML → dados estruturados (dict/list).

O site OLX usa Next.js: muitos dados vêm num <script id="__NEXT_DATA__"> em JSON gigante.
_walk_find_ads percorre esse JSON (dict/list aninhados) e acha objetos que parecem anúncio.
Se não achar o suficiente, fallback: links <a href="/d/..."> no HTML.
"""
from __future__ import annotations

import json
import logging
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
            loc = obj.get("location") or obj.get("address") or {}
            neighborhood = ""
            if isinstance(loc, dict):
                neighborhood = loc.get("neighbourhood") or loc.get("district") or loc.get("name") or ""
            props = obj.get("properties") or []
            bedrooms = None
            area_m2 = None
            if isinstance(props, list):
                for p in props:
                    if not isinstance(p, dict):
                        continue
                    name = (p.get("name") or "").lower()
                    val = p.get("value")
                    if "quarto" in name or name == "bedrooms":
                        try:
                            bedrooms = int(re.sub(r"\D", "", str(val)) or 0)
                        except ValueError:
                            pass
                    if "m²" in str(val) or "area" in name or "área" in name:
                        try:
                            area_m2 = float(re.sub(r"[^\d.,]", "", str(val)).replace(",", "."))
                        except ValueError:
                            pass
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
