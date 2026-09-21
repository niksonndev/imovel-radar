"""
Cliente HTTP para o OLX (cloudscraper) + extração de anúncios via RSC
streaming (App Router / self.__next_f.push).

Cada anúncio é normalizado por ``parser.normalize_olx_listing`` (dict enxuto)
com ``listing_kind`` stampado pela coleta (aluguel | venda).
"""

from __future__ import annotations

import asyncio
import json
import logging
import random
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import cloudscraper
from bs4 import BeautifulSoup
from cloudscraper.exceptions import CloudflareChallengeError

import config
from collector.parser import ListingKind, RawAd, normalize_olx_listing

logger = logging.getLogger(__name__)

_http = cloudscraper.create_scraper()
_cycle_headers: dict[str, str] | None = None

RemainingTimeFn = Callable[[], int | None]


def _extract_rsc_payload(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    chunks: list[str] = []

    for script in soup.find_all("script"):
        script_text = script.string or script.get_text()
        if script.get("id") is not None or "__next_f.push" not in script_text:
            continue

        match = re.search(
            r"self\.__next_f\.push\((\[.*?\])\)\s*$",
            script_text,
            re.DOTALL,
        )
        if not match:
            continue

        try:
            payload = json.loads(match.group(1))
        except json.JSONDecodeError:
            continue

        if (
            isinstance(payload, list)
            and len(payload) >= 2
            and isinstance(payload[0], int)
            and isinstance(payload[1], str)
        ):
            chunks.append(payload[1])

    return "".join(chunks)


def _find_balanced_json(text: str, start_idx: int) -> str:
    if start_idx >= len(text) or text[start_idx] != "[":
        raise ParseError("Índice inicial não aponta para um colchete de abertura")

    depth = 0
    in_string = False
    escaped = False

    for index in range(start_idx, len(text)):
        char = text[index]

        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
        elif char == "[":
            depth += 1
        elif char == "]":
            depth -= 1
            if depth == 0:
                return text[start_idx : index + 1]
            if depth < 0:
                break

    raise ParseError("Array JSON não foi fechado corretamente")


def _extract_ads_candidates(payload: str) -> list[list[dict[str, Any]]]:
    marker = '"ads":['
    candidates: list[list[dict[str, Any]]] = []
    search_start = 0

    while True:
        marker_idx = payload.find(marker, search_start)
        if marker_idx == -1:
            break

        array_start = marker_idx + len(marker) - 1
        search_start = array_start + 1
        try:
            candidate = json.loads(_find_balanced_json(payload, array_start))
        except (json.JSONDecodeError, ParseError):
            continue

        if isinstance(candidate, list):
            candidates.append(candidate)

    return candidates


def _is_empty_results_page(html: str) -> bool:
    """True quando o OLX retorna uma página HTTP 200 sem resultados (fim da listagem)."""
    soup = BeautifulSoup(html, "lxml")
    if config.OLX_EMPTY_RESULTS_TEXT in soup.get_text(" ", strip=True):
        return True

    payload = _extract_rsc_payload(html)
    candidates = _extract_ads_candidates(payload)
    return bool(candidates) and all(len(candidate) == 0 for candidate in candidates)


def _extract_ads_container_from_rsc(html: str) -> dict[str, Any]:
    soup = BeautifulSoup(html, "lxml")
    payload = _extract_rsc_payload(html)
    candidates = _extract_ads_candidates(payload)
    candidates_with_list_id = [
        candidate
        for candidate in candidates
        if any(isinstance(item, dict) and item.get("listId") is not None for item in candidate)
    ]

    if not candidates_with_list_id:
        if _is_empty_results_page(html):
            raise EmptyResultsError(
                "Página sem resultados (fim da listagem) — nenhum anúncio no payload RSC"
            )

        debug_path = Path("debug_last_response.html")
        debug_path.write_text(html, encoding="utf-8")

        title = soup.find("title")

        logger.error(
            "Falha ao extrair anúncios do payload RSC | tamanho_html=%d | "
            "title=%r | candidatos_ads_encontrados=%d | "
            "candidatos_com_listId=%d | html_salvo_em=%s",
            len(html),
            title.string if title else None,
            len(candidates),
            len(candidates_with_list_id),
            debug_path.resolve(),
        )

        raise ParseError("Nenhum array de anúncios válido encontrado no payload RSC")

    return {"ads": max(candidates_with_list_id, key=len)}


def _extract_ads_payload(ads_container: dict[str, Any]) -> list[dict[str, Any]]:
    try:
        ads = ads_container["ads"]
    except KeyError as e:
        raise ParseError(f"Caminho ausente no payload de anúncios extraído do RSC: {e}") from e

    if not isinstance(ads, list):
        raise ParseError("`ads` no payload de anúncios extraído do RSC não é uma lista")

    return [item for item in ads if isinstance(item, dict)]


def extract_listings_from_search_page(
    html: str,
    *,
    listing_kind: ListingKind = "aluguel",
) -> list[RawAd]:
    ads_container = _extract_ads_container_from_rsc(html)
    ads = _extract_ads_payload(ads_container)

    listings: list[RawAd] = []
    for ad in ads:
        if ad.get("listId") is None:
            continue

        listing = normalize_olx_listing(ad, listing_kind=listing_kind)
        if not listing["images"]:
            continue

        listings.append(listing)

    return listings


def _listings_url(base_url: str, page: int) -> str:
    if page <= 1:
        return base_url
    return f"{base_url}?o={page}"


def base_url_for_kind(listing_kind: ListingKind) -> str:
    if listing_kind == "venda":
        return config.MACEIO_SALE_LISTINGS_URL
    return config.MACEIO_RENT_LISTINGS_URL


class FetchError(Exception):
    def __init__(self, status_code: int, url: str) -> None:
        self.status_code = status_code
        self.url = url
        super().__init__(f"HTTP {status_code} para {url}")


class ParseError(Exception):
    pass


class EmptyResultsError(ParseError):
    """Página HTTP 200 válida, porém sem resultados — marca o fim da listagem."""


@dataclass
class SearchChunkResult:
    """Resultado de uma janela de páginas (uma invocação Lambda)."""

    listings: list[RawAd] = field(default_factory=list)
    next_page: int | None = None
    completed: bool = False
    listing_kind: ListingKind = "aluguel"


async def close() -> None:
    _http.close()


async def _delay() -> None:
    await asyncio.sleep(random.uniform(config.SCRAPER_DELAY_MIN, config.SCRAPER_DELAY_MAX))


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
        r = _http.get(url, timeout=90, headers=headers)
    except CloudflareChallengeError as e:
        logger.error("CloudflareChallengeError em _sync_get / cloudscraper.get(%s): %s", url, e)
        raise
    return r.status_code, r.text


async def fetch(url: str, headers: dict[str, str] | None = None) -> str:
    await _delay()
    req_headers = headers or _cycle_headers or _build_headers()
    try:
        status_code, text = await asyncio.to_thread(_sync_get, url, req_headers)
    except CloudflareChallengeError as e:
        logger.error("CloudflareChallengeError em fetch (%s): %s", url, e)
        raise
    if status_code >= 400:
        raise FetchError(status_code, url)
    return text


def _out_of_time(get_remaining_ms: RemainingTimeFn | None) -> bool:
    if get_remaining_ms is None:
        return False
    remaining = get_remaining_ms()
    if remaining is None:
        return False
    return remaining < config.SCRAPER_REMAINING_TIME_BUDGET_MS


async def search_listings(
    base_url: str,
    *,
    listing_kind: ListingKind,
    start_page: int = 1,
    max_pages: int | None = None,
    get_remaining_ms: RemainingTimeFn | None = None,
) -> SearchChunkResult:
    """Coleta uma janela de páginas a partir de ``start_page``.

    Para em: página vazia (``completed=True``), limite de páginas da janela
    (``next_page`` preenchido), tempo restante da Lambda, ou erro de fetch/parse.
    """
    global _cycle_headers
    window = max_pages if max_pages is not None else config.SCRAPER_PAGES_PER_INVOKE
    hard_cap = config.SCRAPER_MAX_PAGES
    listings_by_id: dict[int, RawAd] = {}
    _cycle_headers = _build_headers()
    page = max(1, start_page)
    pages_in_window = 0
    completed = False
    next_page: int | None = None

    try:
        while pages_in_window < window and page <= hard_cap:
            if _out_of_time(get_remaining_ms):
                logger.info(
                    "Tempo restante insuficiente — pausando em página %s (kind=%s)",
                    page,
                    listing_kind,
                )
                next_page = page
                break

            url = _listings_url(base_url, page)
            try:
                html = await fetch(url)
            except CloudflareChallengeError:
                next_page = page
                break
            except Exception as e:
                logger.exception("Erro ao buscar %s: %s", url, e)
                next_page = page
                break

            try:
                page_listings = extract_listings_from_search_page(
                    html, listing_kind=listing_kind
                )
            except EmptyResultsError:
                logger.info(
                    "Página %s: fim da listagem (sem resultados) — kind=%s",
                    page,
                    listing_kind,
                )
                completed = True
                break
            except ParseError as e:
                logger.exception("Erro ao extrair listings de %s: %s", url, e)
                next_page = page
                break
            except Exception as e:
                logger.exception("Erro ao extrair listings de %s: %s", url, e)
                next_page = page
                break

            logger.info(
                "Página %s: %s listings extraídos (kind=%s)",
                page,
                len(page_listings),
                listing_kind,
            )
            if not page_listings:
                completed = True
                break

            new_listing_count = 0
            for listing in page_listings:
                listing_id = listing["listing_id"]
                if listing_id not in listings_by_id:
                    new_listing_count += 1
                listings_by_id[listing_id] = listing

            if new_listing_count == 0:
                completed = True
                break

            pages_in_window += 1
            page += 1
        else:
            if not completed and page <= hard_cap:
                next_page = page
            elif page > hard_cap:
                completed = True
    finally:
        _cycle_headers = None
        await close()

    listings = list(listings_by_id.values())
    logger.info(
        "Chunk kind=%s: %s listings | completed=%s | next_page=%s",
        listing_kind,
        len(listings),
        completed,
        next_page,
    )
    return SearchChunkResult(
        listings=listings,
        next_page=next_page,
        completed=completed,
        listing_kind=listing_kind,
    )


async def search_all_rent_maceio() -> list[RawAd]:
    """Compat: coleta aluguel Maceió até o fim (sem janela de invocação)."""
    result = await search_listings(
        config.MACEIO_RENT_LISTINGS_URL,
        listing_kind="aluguel",
        start_page=1,
        max_pages=config.SCRAPER_MAX_PAGES,
    )
    return result.listings


def coletar() -> list[RawAd]:
    return asyncio.run(search_all_rent_maceio())
