"""
Cliente HTTP para o OLX (cloudscraper) + HTML → dict via parser.py.

A listagem é sempre aluguel Maceió; filtragem fica a cargo do parser (ou camadas acima).
"""
from __future__ import annotations

import asyncio
import logging
import random
from typing import Any

import cloudscraper

import config
from scraper.parser import parse_listing_page, parse_search_page

logger = logging.getLogger(__name__)

BASE = "https://www.olx.com.br"
MACEIO_RENT_LISTINGS_URL = (
    "https://www.olx.com.br/imoveis/aluguel/estado-al/alagoas/maceio"
)

_http = cloudscraper.create_scraper()
_cycle_headers: dict[str, str] | None = None


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


async def search_listings_maceio_rent(max_pages: int | None = 15) -> list[dict]:
    """
    A partir da página 1 (sem query). Seguintes: ?o=2, ?o=3, ...
    Deduplica por olx_id; sem filtros locais (parser/job decidem depois).
    """
    global _cycle_headers
    all_ads: dict[str, dict] = {}
    _cycle_headers = _build_headers()
    try:
        page = 1
        while True:
            if max_pages is not None and page > max_pages:
                break
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
                oid = ad["olx_id"]
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


async def search_all_rent_maceio() -> list[dict]:
    return await search_listings_maceio_rent(max_pages=None)


async def fetch_listing(url: str) -> dict[str, Any]:
    """Uma página de anúncio (watchlist / detalhe)."""
    if not url.startswith("http"):
        url = BASE + url
    try:
        html = await fetch(url)
    except FetchError as e:
        if e.status_code == 404:
            return {"removed": True, "not_found": True, "price": None, "title": None}
        raise
    return parse_listing_page(html)
