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
from typing import Any

import cloudscraper
from cloudscraper.exceptions import CloudflareChallengeError
from bs4 import BeautifulSoup

import config
from scraper.parser import normalize_olx_listing
from utils.models import Listing

logger = logging.getLogger(__name__)

_http = cloudscraper.create_scraper()
_cycle_headers: dict[str, str] | None = None


def _extract_next_data(html: str) -> dict[str, Any]:
    script = BeautifulSoup(html, "lxml").find("script", id="__NEXT_DATA__")
    if not script or not script.string:
        raise ParseError('Tag <script id="__NEXT_DATA__"> não encontrada ou vazia')

    try:
        return json.loads(script.string)
    except json.JSONDecodeError as e:
        raise ParseError(f"Falha ao decodificar __NEXT_DATA__: {e}") from e


def _extract_ads_payload(next_data: dict[str, Any]) -> list[dict[str, Any]]:
    try:
        ads = next_data["props"]["pageProps"]["ads"]
    except KeyError as e:
        raise ParseError(f"Caminho ausente no __NEXT_DATA__: {e}") from e

    if not isinstance(ads, list):
        raise ParseError("`props.pageProps.ads` não é uma lista")

    return [item for item in ads if isinstance(item, dict)]


def extract_listings_from_search_page(html: str) -> list[Listing]:
    """HTML da listagem → lista de anúncios (formato normalizado)."""
    next_data = _extract_next_data(html)
    ads = _extract_ads_payload(next_data)

    listings: list[Listing] = []
    for ad in ads:
        if ad.get("listId") is None:
            continue
        listings.append(normalize_olx_listing(ad))
    return listings


def _rent_maceio_listings_url(page: int) -> str:
    """Página 1 = URL limpa; páginas seguintes ?o= (paginação OLX)."""
    base = config.MACEIO_RENT_LISTINGS_URL
    if page <= 1:
        return base
    return f"{base}?o={page}"


class FetchError(Exception):
    """Erro HTTP retornado pelo servidor."""

    def __init__(self, status_code: int, url: str) -> None:
        self.status_code = status_code
        self.url = url
        super().__init__(f"HTTP {status_code} para {url}")


class ParseError(Exception):
    """Erro ao extrair listings do HTML da busca."""


async def close() -> None:
    """Fecha o cliente HTTP global do cloudscraper."""
    _http.close()


async def _delay() -> None:
    await asyncio.sleep(
        random.uniform(config.SCRAPER_DELAY_MIN, config.SCRAPER_DELAY_MAX)
    )


def _build_headers() -> dict[str, str]:
    user_agent = random.choice(config.USER_AGENTS)
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
        "Referer": config.OLX_REFERER,
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1",
        "Connection": "keep-alive",
    }


def _sync_get(url: str, headers: dict[str, str]) -> tuple[int, str]:
    try:
        r = _http.get(
            url,
            timeout=90,
            headers=headers,
        )
    except CloudflareChallengeError as e:
        logger.error(
            "CloudflareChallengeError em _sync_get / cloudscraper.get(%s): %s",
            url,
            e,
        )
        raise
    return r.status_code, r.text


async def fetch(url: str, headers: dict[str, str] | None = None) -> str:
    """GET assíncrono com delay; retorna HTML ou levanta ``FetchError`` se HTTP >= 400."""
    await _delay()
    req_headers = headers or _cycle_headers or _build_headers()
    try:
        status_code, text = await asyncio.to_thread(_sync_get, url, req_headers)
    except CloudflareChallengeError as e:
        logger.error(
            "CloudflareChallengeError em fetch após asyncio.to_thread (%s): %s",
            url,
            e,
        )
        raise
    if status_code >= 400:
        raise FetchError(status_code, url)
    return text


async def search_all_rent_maceio() -> list[Listing]:
    """
    Todas as páginas de aluguel Maceió (1, depois ?o=2, ?o=3, ...).
    Deduplica por listId; sem filtros locais (job decidem depois).
    """
    global _cycle_headers
    all_ads: dict[int, Listing] = {}
    _cycle_headers = _build_headers()
    try:
        page = 1
        while True:
            url = _rent_maceio_listings_url(page)
            try:
                html = await fetch(url)
            except CloudflareChallengeError:
                break
            except Exception as e:
                logger.exception("Erro ao buscar %s: %s", url, e)
                break
            ads = extract_listings_from_search_page(html)
            logger.info("Página %s: %s anúncios brutos", page, len(ads))
            if not ads:
                break
            new_in_page = 0
            for ad in ads:
                list_id = ad["listId"]
                if list_id not in all_ads:
                    new_in_page += 1
                all_ads[list_id] = ad
            if new_in_page == 0:
                break
            page += 1
    finally:
        _cycle_headers = None
        await close()
    out = list(all_ads.values())
    logger.info("Total anúncios únicos (scraping): %s", len(out))
    return out


def coletar() -> list[Listing]:
    """Executa a coleta síncrona (útil em threads sem event loop asyncio ativo)."""
    return asyncio.run(search_all_rent_maceio())
