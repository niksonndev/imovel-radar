"""
Cliente HTTP para o OLX (cloudscraper) + extração de anúncios via RSC
streaming (App Router / self.__next_f.push).

A listagem é sempre aluguel Maceió; cada anúncio é normalizado por
``parser.normalize_olx_listing`` (dict enxuto).
"""

from __future__ import annotations

import asyncio
import json
import logging
import random
import re
from pathlib import Path
from typing import Any

import cloudscraper
from bs4 import BeautifulSoup
from cloudscraper.exceptions import CloudflareChallengeError

import config
from models import Listing
from scraper.parser import normalize_olx_listing

logger = logging.getLogger(__name__)

_http = cloudscraper.create_scraper()
_cycle_headers: dict[str, str] | None = None


def _extract_rsc_payload(html: str) -> str:
    """Concatena todos os chunks de self.__next_f.push(...) presentes no HTML,
    na ordem em que aparecem, retornando uma única string."""
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
    """A partir de start_idx (índice do caractere '[' de abertura), retorna
    a substring balanceada correspondente, respeitando aspas e escapes
    dentro de strings. Levanta ParseError se não fechar corretamente."""
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
    """Encontra todas as ocorrências de '"ads":[' no payload RSC, faz
    bracket-matching em cada uma a partir do '[' de abertura, tenta
    json.loads, e retorna a lista de arrays decodificados com sucesso
    (ignora silenciosamente os que falharem no parse)."""
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


def _extract_ads_container_from_rsc(html: str) -> dict[str, Any]:
    """Extrai do RSC o maior array ``ads`` que contém itens com ``listId``."""
    soup = BeautifulSoup(html, "lxml")
    payload = _extract_rsc_payload(html)
    candidates = _extract_ads_candidates(payload)
    candidates_with_list_id = [
        candidate
        for candidate in candidates
        if any(isinstance(item, dict) and item.get("listId") is not None for item in candidate)
    ]

    if not candidates_with_list_id:
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
    """Valida e retorna os objetos do array ``ads`` extraído do RSC."""
    try:
        ads = ads_container["ads"]
    except KeyError as e:
        raise ParseError(f"Caminho ausente no payload de anúncios extraído do RSC: {e}") from e

    if not isinstance(ads, list):
        raise ParseError("`ads` no payload de anúncios extraído do RSC não é uma lista")

    return [item for item in ads if isinstance(item, dict)]


def extract_listings_from_search_page(html: str) -> list[Listing]:
    """HTML da listagem → lista de anúncios (formato normalizado)."""
    ads_container = _extract_ads_container_from_rsc(html)
    ads = _extract_ads_payload(ads_container)

    listings: list[Listing] = []
    for ad in ads:
        if ad.get("listId") is None:
            continue
        listing = normalize_olx_listing(ad)
        if not json.loads(listing["images"]):
            continue
        listing = normalize_olx_listing(ad)
        listings.append(listing)
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
    listings_by_id: dict[int, Listing] = {}
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
            try:
                page_listings = extract_listings_from_search_page(html)
            except Exception as e:
                logger.exception("Erro ao extrair listings de %s: %s", url, e)
                break

            logger.info("Página %s: %s listings extraídos", page, len(page_listings))
            if not page_listings:
                break

            new_listing_count = 0
            for listing in page_listings:
                list_id = listing["listId"]
                if list_id not in listings_by_id:
                    new_listing_count += 1
                listings_by_id[list_id] = listing

            if new_listing_count == 0:
                break
            page += 1
    finally:
        _cycle_headers = None
        await close()

    listings = list(listings_by_id.values())
    logger.info("Total listings únicos (scraping): %s", len(listings))
    return listings


def coletar() -> list[Listing]:
    """Executa a coleta síncrona (útil em threads sem event loop asyncio ativo)."""
    return asyncio.run(search_all_rent_maceio())
