"""
Cliente HTTP para o OLX (cloudscraper) + extração de __NEXT_DATA__ / fallback HTML.

A listagem é sempre aluguel Maceió; cada anúncio é normalizado por
``parser.normalize_olx_listing`` (dict enxuto).
"""
from __future__ import annotations

import asyncio
import json
import logging
import random
import re
from typing import Any

import cloudscraper
from bs4 import BeautifulSoup

import config
from scraper.parser import normalize_olx_listing

logger = logging.getLogger(__name__)

BASE = "https://www.olx.com.br"
OLX_ID_RE = re.compile(r"/(\d{8,})(?:\?|$|/)", re.I)
MACEIO_RENT_LISTINGS_URL = (
    "https://www.olx.com.br/imoveis/aluguel/estado-al/alagoas/maceio"
)

_http = cloudscraper.create_scraper()
_cycle_headers: dict[str, str] | None = None


def _normalize_url(href: str) -> str:
    if href.startswith("http"):
        return href.split("?")[0].rstrip("/")
    return BASE + href.split("?")[0].rstrip("/")


def _walk_collect_listings(obj: Any, out: list[dict], depth: int = 0) -> None:
    """Percorre JSON do __NEXT_DATA__ e acumula dicts normalizados com listId válido."""
    if depth > 25 or obj is None:
        return
    if isinstance(obj, dict):
        lid = str(obj.get("listId") or obj.get("adId") or "")
        if not lid.isdigit() or len(lid) < 6:
            if isinstance(obj.get("url"), str):
                m = OLX_ID_RE.search(obj["url"])
                lid = m.group(1) if m else ""
        if lid.isdigit() and len(lid) >= 6:
            normalized = normalize_olx_listing(obj)
            if normalized.get("listId") is not None:
                out.append(normalized)
        for v in obj.values():
            _walk_collect_listings(v, out, depth + 1)
    elif isinstance(obj, list):
        for item in obj:
            _walk_collect_listings(item, out, depth + 1)


def parse_search_page(html: str) -> list[dict]:
    """HTML da listagem → lista de anúncios (formato normalizado)."""
    out: list[dict] = []
    seen_ids: set[str] = set()

    soup = BeautifulSoup(html, "lxml")
    script = soup.find("script", id="__NEXT_DATA__")
    if script and script.string:
        try:
            data = json.loads(script.string)
            _walk_collect_listings(data, out)
        except json.JSONDecodeError as e:
            logger.warning("__NEXT_DATA__ JSON: %s", e)

    dedup: dict[str, dict] = {}
    for ad in out:
        lid = ad.get("listId")
        oid = str(lid) if lid is not None else ""
        if not oid or oid in seen_ids:
            continue
        if oid not in dedup or (
            ad.get("url") and "olx.com.br/d/" in str(ad.get("url"))
        ):
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
                "listId": int(oid),
                "url": _normalize_url(href),
                "title": (a.get_text() or "Anúncio")[:500],
                "priceValue": None,
                "oldPrice": None,
                "municipality": "",
                "neighbourhood": "",
                "properties": [],
                "category": "",
                "images": [],
            }
        result = list(dedup.values())

    return result


def _rent_maceio_listings_url(page: int) -> str:
    """Página 1 = URL limpa; páginas seguintes ?o= (paginação OLX)."""
    if page <= 1:
        return MACEIO_RENT_LISTINGS_URL
    return f"{MACEIO_RENT_LISTINGS_URL}?o={page}"


class FetchError(Exception):
    """Erro HTTP retornado pelo servidor."""

    def __init__(self, status_code: int, url: str) -> None:
        self.status_code = status_code
        self.url = url
        super().__init__(f"HTTP {status_code} para {url}")


async def close() -> None:
    _http.close()


async def _delay() -> None:
    await asyncio.sleep(random.uniform(config.SCRAPER_DELAY_MIN, config.SCRAPER_DELAY_MAX))


def _build_headers() -> dict[str, str]:
    user_agents = config.USER_AGENTS or [
        (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
    ]
    user_agent = random.choice(user_agents)
    return {
        "User-Agent": user_agent,
        "Accept": (
            "text/html,application/xhtml+xml,application/xml;q=0.9,"
            "image/avif,image/webp,image/apng,*/*;q=0.8"
        ),
        "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept-Encoding": "gzip, deflate, br",
        "Cache-Control": "max-age=0",
        "Pragma": "no-cache",
        "Referer": "https://www.olx.com.br/",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1",
        "Connection": "keep-alive",
    }


def _sync_get(url: str, headers: dict[str, str]) -> tuple[int, str]:
    r = _http.get(
        url,
        timeout=90,
        headers=headers,
    )
    return r.status_code, r.text


async def fetch(url: str, headers: dict[str, str] | None = None) -> str:
    await _delay()
    req_headers = headers or _cycle_headers or _build_headers()
    status_code, text = await asyncio.to_thread(_sync_get, url, req_headers)
    if status_code >= 400:
        raise FetchError(status_code, url)
    return text


async def search_all_rent_maceio() -> list[dict]:
    """
    Todas as páginas de aluguel Maceió (1, depois ?o=2, ?o=3, ...).
    Deduplica por listId; sem filtros locais (job decidem depois).
    """
    global _cycle_headers
    all_ads: dict[str, dict] = {}
    _cycle_headers = _build_headers()
    try:
        page = 1
        while True:
            url = _rent_maceio_listings_url(page)
            try:
                html = await fetch(url)
            except Exception as e:
                logger.exception("Erro ao buscar %s: %s", url, e)
                break
            ads = parse_search_page(html)
            logger.info("Página %s: %s anúncios brutos", page, len(ads))
            if not ads:
                break
            new_in_page = 0
            for ad in ads:
                lid = ad.get("listId")
                oid = str(lid) if lid is not None else ""
                if not oid:
                    continue
                if oid not in all_ads:
                    new_in_page += 1
                all_ads[oid] = ad
            if new_in_page == 0:
                break
            page += 1
    finally:
        _cycle_headers = None
    out = list(all_ads.values())
    logger.info("Total anúncios únicos (scraping): %s", len(out))
    return out
