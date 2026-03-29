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

logger = logging.getLogger(__name__)

_http = cloudscraper.create_scraper()
_cycle_headers: dict[str, str] | None = None


def _walk_collect_listings(obj: Any, out: list[dict], depth: int = 0) -> None:
    """Percorre JSON do __NEXT_DATA__ e acumula anúncios normalizados.
    A ideia é deixar `normalize_olx_listing` (parser.py) com a responsabilidade de:
    - descobrir `listId` / `adId`
    - validar/filtrar
    - normalizar `url`, `properties`, `images`, etc.
    """
    if depth > 25 or obj is None:
        return
    if isinstance(obj, dict):
        # Heurística mínima para reduzir chamadas de normalização:
        # objetos com `listId`/`adId` ou com URL de anúncio (/d/).
        has_explicit_id = obj.get("listId") is not None or obj.get("adId") is not None
        url_val = (
            obj.get("url")
            if isinstance(obj.get("url"), str)
            else obj.get("friendlyUrl")
        )
        has_url_hint = isinstance(url_val, str) and "/d/" in url_val
        if has_explicit_id or has_url_hint:
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
            # Fallback quando o `__NEXT_DATA__` falha/retorna pouco:
            # reaproveita o parser para garantir o formato fixo.
            raw = {
                "url": href,
                "friendlyUrl": href,
                "title": a.get_text() or "Anúncio",
            }
            normalized = normalize_olx_listing(raw)
            oid = normalized.get("listId")
            if oid is None:
                continue
            oid_s = str(oid)
            if oid_s in dedup:
                continue
            dedup[oid_s] = normalized
        result = list(dedup.values())

    return result


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
            except CloudflareChallengeError:
                break
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
