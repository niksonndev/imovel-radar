"""
Cliente HTTP para o OLX (curl_cffi, impersonate Chrome 150) + extração de
anúncios via RSC streaming (App Router).

A listagem é pedida com ``RSC: 1`` / ``Accept: text/x-component``: a resposta vem
como flight cru (``text/x-component``, ~270 KB) em vez do HTML renderizado
(~1,0 MB). O caminho HTML continua suportado (``__next_f.push``).

O fingerprint TLS/HTTP2 e os headers de navegador (User-Agent, Accept-Language,
sec-ch-ua, Sec-Fetch-*) vêm do ``impersonate`` do curl_cffi — não são montados à
mão.

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
from urllib.parse import urlencode, urlsplit, urlunsplit

from bs4 import BeautifulSoup
from curl_cffi.requests import Session
from curl_cffi.requests.exceptions import RequestException

import config
from collector.parser import ListingKind, RawAd, normalize_olx_listing

logger = logging.getLogger(__name__)

# Preset do curl_cffi usado na sessão. Fixo (não o alias "chrome"): o alias
# acompanha a versão do pacote, o preset explícito é reprodutível com o pin.
IMPERSONATE = "chrome150"

# A listagem responde o HTML renderizado (~1,0 MB) por padrão; com estes headers
# o App Router devolve o flight cru (~270 KB) com os mesmos dados.
RSC_HEADERS = {"RSC": "1", "Accept": "text/x-component"}

_http: Session | None = None
_cycle_headers: dict[str, str] | None = None

# Lambda: o cwd é read-only. Dump de debug (flight ou HTML) vai para /tmp.
DEBUG_HTML_PATH = Path("/tmp/debug_last_response.html")
_RETRYABLE_HTTP = frozenset({403, 429, 502})

# Marcadores de página de challenge do Cloudflare. O cloudscraper detectava
# isso e levantava CloudflareChallengeError; com curl_cffi é heurística nossa,
# porque um bloqueio também chega como HTTP 200 com corpo de desafio.
_CHALLENGE_MARKERS = (
    "cf-chl",
    "challenge-platform",
    "Just a moment",
    "__cf_chl",
)

RemainingTimeFn = Callable[[], int | None]


# Cada chunk do flight é prefixado pelo tamanho em hexa (`1:"$Sreact.fragment"`,
# `2:I[496659,...]`). O HTML renderizado começa com `<!DOCTYPE html>`.
_FLIGHT_CHUNK_PREFIX = re.compile(r"^[0-9a-f]{1,6}:")


def _is_flight(text: str) -> bool:
    """True quando o corpo é o flight cru do App Router (``text/x-component``).

    A listagem é pedida com ``RSC: 1`` e volta assim (~4x menor que o HTML); o
    HTML renderizado carrega os mesmos dados em ``self.__next_f.push``.
    """
    return _FLIGHT_CHUNK_PREFIX.match(text) is not None


def _extract_rsc_payload(text: str) -> str:
    """Payload RSC, do flight cru ou dos chunks ``__next_f.push`` do HTML.

    No flight o corpo inteiro já é o payload (~4x menor que o HTML); no HTML é
    preciso concatenar os chunks injetados pelo App Router.
    """
    if _is_flight(text):
        return text

    soup = BeautifulSoup(text, "lxml")
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


def _is_empty_results_page(text: str) -> bool:
    """True quando o OLX retorna uma página HTTP 200 sem resultados (fim da listagem)."""
    if not _is_flight(text):
        # Só o HTML renderizado traz o texto do estado vazio.
        soup = BeautifulSoup(text, "lxml")
        if config.OLX_EMPTY_RESULTS_TEXT in soup.get_text(" ", strip=True):
            return True

    candidates = _extract_ads_candidates(_extract_rsc_payload(text))
    return bool(candidates) and all(len(candidate) == 0 for candidate in candidates)


def _extract_ads_container_from_rsc(body: str) -> dict[str, Any]:
    payload = _extract_rsc_payload(body)
    candidates = _extract_ads_candidates(payload)
    candidates_with_list_id = [
        candidate
        for candidate in candidates
        if any(isinstance(item, dict) and item.get("listId") is not None for item in candidate)
    ]

    if not candidates_with_list_id:
        if _is_empty_results_page(body):
            raise EmptyResultsError(
                "Página sem resultados (fim da listagem) — nenhum anúncio no payload RSC"
            )

        saved = _dump_debug_html(body)

        logger.error(
            "Falha ao extrair anúncios do payload RSC | tamanho=%d | flight=%s | "
            "fullPageTitle=%r | candidatos_ads_encontrados=%d | "
            "candidatos_com_listId=%d | resposta_salva_em=%s",
            len(body),
            _is_flight(body),
            _full_page_title(body),
            len(candidates),
            len(candidates_with_list_id),
            saved or "não salvo",
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
    body: str,
    *,
    listing_kind: ListingKind = "aluguel",
) -> list[RawAd]:
    ads_container = _extract_ads_container_from_rsc(body)
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


def _dump_debug_html(html: str) -> str | None:
    """Grava o HTML de debug. Falha de disco não vira exceção (cwd da Lambda é read-only)."""
    try:
        DEBUG_HTML_PATH.write_text(html, encoding="utf-8")
    except OSError as exc:
        logger.error(
            "Não foi possível salvar HTML de debug em %s: %s",
            DEBUG_HTML_PATH,
            exc,
        )
        return None
    return str(DEBUG_HTML_PATH)


def _listings_url(
    base_url: str,
    page: int,
    *,
    price_min: int | None = None,
    price_max: int | None = None,
) -> str:
    """URL de listagem ordenada por mais recentes (``sf=1``), com preço e página.

    A query é montada do zero: ``base?sf=1&o=2`` (nunca ``base?sf=1?o=2``).
    ``ps`` = preço mínimo, ``pe`` = preço máximo (inclusivos na OLX).
    """
    parts = urlsplit(base_url)
    params: list[tuple[str, str]] = [("sf", "1")]
    if price_min is not None:
        params.append(("ps", str(int(price_min))))
    if price_max is not None:
        params.append(("pe", str(int(price_max))))
    if page > 1:
        params.append(("o", str(page)))
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(params), ""))


_PAGE_IN_TITLE = re.compile(r"Página\s+(\d+)", re.IGNORECASE)
# O flight carrega o título completo da listagem (com "Página N"), o mesmo que
# vira `<title>` no HTML renderizado.
_FLIGHT_FULL_PAGE_TITLE = re.compile(r'"fullPageTitle":"((?:[^"\\]|\\.)*)"')


def _full_page_title(text: str) -> str | None:
    """Título completo da listagem — ``fullPageTitle`` do flight ou ``<title>``."""
    match = _FLIGHT_FULL_PAGE_TITLE.search(text)
    if match is not None:
        return match.group(1)

    if _is_flight(text):
        return None

    soup = BeautifulSoup(text, "lxml")
    title = soup.find("title")
    if title is None:
        return None
    return title.get_text(" ", strip=True)


def _page_number_from_title(title: str) -> int | None:
    match = _PAGE_IN_TITLE.search(title)
    if match is None:
        return None
    return int(match.group(1))


def returned_page_number(body: str) -> int | None:
    """Número de página que a OLX informou na resposta, quando informa.

    Página 1 não traz o número (retorna ``None``); ``o=101`` volta como
    "Página 100".
    """
    title = _full_page_title(body)
    if title is None:
        return None
    return _page_number_from_title(title)


def is_clamped_page(body: str, requested_page: int) -> bool:
    """True quando a OLX devolve uma página anterior à pedida (teto da listagem).

    ``o=101`` volta com título "Página 100" e os mesmos anúncios. Isso não é
    fim de listagem: marcar ``completed`` dispararia deactivate do que ficou de fora.
    """
    if requested_page <= 1:
        return False
    returned = returned_page_number(body)
    return returned is not None and returned < requested_page


def base_url_for_kind(listing_kind: ListingKind, *, market_key: str | None = None) -> str:
    market = config.market_by_key(market_key)
    if listing_kind == "venda":
        return market.sale_url
    return market.rent_url


class FetchError(Exception):
    def __init__(self, status_code: int, url: str) -> None:
        self.status_code = status_code
        self.url = url
        super().__init__(f"HTTP {status_code} para {url}")


class ParseError(Exception):
    pass


class EmptyResultsError(ParseError):
    """Página HTTP 200 válida, porém sem resultados — marca o fim da listagem."""


class TransientFetchError(Exception):
    """Falha retryável da camada HTTP (rede ou challenge Cloudflare)."""


@dataclass
class SearchChunkResult:
    """Resultado de uma janela de páginas (uma invocação Lambda)."""

    listings: list[RawAd] = field(default_factory=list)
    next_page: int | None = None
    completed: bool = False
    listing_kind: ListingKind = "aluguel"
    # Tentativas já gastas na página ``next_page`` (0 quando a página avança).
    next_attempt: int = 0
    # OLX devolveu uma página anterior à pedida. Não é fim de listagem.
    clamped: bool = False


async def close() -> None:
    """Encerra a sessão HTTP do módulo; a próxima coleta reabre uma nova.

    O curl_cffi recusa requisições numa Session já fechada (``SessionClosed``) e
    ``search_listings`` chama ``close()`` no fim de cada janela: sem reabrir, a
    segunda coleta no mesmo processo (container quente da Lambda, testes,
    ``search_all_rent_maceio`` em sequência) falharia.
    """
    global _http
    session, _http = _http, None
    if session is not None:
        session.close()


def _get_session() -> Session:
    """Sessão única do processo, recriada depois de ``close()``."""
    global _http
    session = _http
    if session is None:
        session = Session(impersonate=IMPERSONATE, default_encoding="utf-8")
        _http = session
    return session


async def _delay() -> None:
    await asyncio.sleep(random.uniform(config.SCRAPER_DELAY_MIN, config.SCRAPER_DELAY_MAX))


def _build_headers() -> dict[str, str]:
    """Headers extras sobre o fingerprint do curl_cffi.

    User-Agent, Accept-Language, Accept-Encoding e Sec-Fetch-* vêm do
    ``impersonate`` — não sobrescrever (UA aleatório de outro navegador
    invalidaria o fingerprint). O ``Accept`` é trocado pelo do flight.
    """
    return {**RSC_HEADERS, "Referer": config.OLX_REFERER}


def _looks_like_challenge(text: str) -> bool:
    """True quando o corpo é uma página de challenge do Cloudflare."""
    return any(marker in text for marker in _CHALLENGE_MARKERS)


def _sync_get(url: str, headers: dict[str, str]) -> tuple[int, str]:
    """GET síncrono (roda em thread). Falha de rede vira erro retryável."""
    try:
        r = _get_session().get(url, timeout=90, headers=headers)
    except RequestException as e:
        raise TransientFetchError(f"falha de rede em {url}: {e}") from e
    return r.status_code, r.text


async def fetch(url: str, headers: dict[str, str] | None = None) -> str:
    """GET com delay.

    403/429/502, falha de rede (``RequestException`` do curl_cffi) e challenge
    do Cloudflare em HTTP 200 são retentados com pausa maior e headers novos.
    """
    retries = max(1, config.SCRAPER_FETCH_RETRIES)
    for try_index in range(retries):
        if try_index == 0:
            await _delay()
            req_headers = headers or _cycle_headers or _build_headers()
        else:
            await asyncio.sleep(config.SCRAPER_DELAY_MAX * try_index)
            req_headers = _build_headers()

        reason: str | None = None
        try:
            status_code, text = await asyncio.to_thread(_sync_get, url, req_headers)
        except TransientFetchError as e:
            logger.warning("Falha transitória em %s: %s", url, e)
            status_code, text = 0, ""
            reason = str(e)

        if status_code == 200 and _looks_like_challenge(text):
            reason = "corpo de challenge do Cloudflare"
            status_code = 0

        if status_code in _RETRYABLE_HTTP or status_code == 0:
            if try_index + 1 < retries:
                logger.warning(
                    "HTTP %s em %s (%s) — nova tentativa (%s/%s)",
                    status_code,
                    url,
                    reason or "status retryável",
                    try_index + 1,
                    retries,
                )
                continue
            raise FetchError(status_code, url)
        if status_code >= 400:
            raise FetchError(status_code, url)
        return text
    raise FetchError(0, url)


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
    price_min: int | None = None,
    price_max: int | None = None,
    attempt: int = 0,
    get_remaining_ms: RemainingTimeFn | None = None,
) -> SearchChunkResult:
    """Coleta uma janela de páginas a partir de ``start_page``.

    Para em: página vazia (``completed=True``), limite de páginas da janela
    (``next_page`` preenchido), tempo restante da Lambda, erro de fetch/parse,
    ou clamp da OLX (``clamped=True``, sem ``completed``).
    ``attempt`` conta falhas anteriores da página inicial; após
    ``SCRAPER_PAGE_MAX_ATTEMPTS`` a página é pulada (sem ``completed``).
    """
    global _cycle_headers
    window = max_pages if max_pages is not None else config.SCRAPER_PAGES_PER_INVOKE
    hard_cap = config.SCRAPER_MAX_PAGES
    max_attempts = max(1, config.SCRAPER_PAGE_MAX_ATTEMPTS)
    listings_by_id: dict[int, RawAd] = {}
    _cycle_headers = _build_headers()
    retry_page = max(1, start_page)
    retry_attempt = max(0, attempt)
    page = retry_page
    pages_in_window = 0
    completed = False
    clamped = False
    next_page: int | None = None
    next_attempt = 0

    def _fail(page_attempt: int) -> bool:
        """Registra falha da página atual. True = interromper a janela e reenfileirar."""
        nonlocal page, next_page, next_attempt
        failed = page_attempt + 1
        if failed >= max_attempts:
            logger.warning(
                "Página %s falhou %s vezes (kind=%s) — pulando para a próxima",
                page,
                failed,
                listing_kind,
            )
            page += 1
            return False
        next_page = page
        next_attempt = failed
        return True

    try:
        while pages_in_window < window and page <= hard_cap:
            if _out_of_time(get_remaining_ms):
                logger.info(
                    "Tempo restante insuficiente — pausando em página %s (kind=%s)",
                    page,
                    listing_kind,
                )
                next_page = page
                next_attempt = retry_attempt if page == retry_page else 0
                break

            page_attempt = retry_attempt if page == retry_page else 0
            url = _listings_url(
                base_url,
                page,
                price_min=price_min,
                price_max=price_max,
            )
            try:
                body = await fetch(url)
            except Exception as e:
                logger.exception("Erro ao buscar %s: %s", url, e)
                if _fail(page_attempt):
                    break
                continue

            if is_clamped_page(body, page):
                logger.error(
                    "OLX clampou a página %s (kind=%s) — encerrando a fatia sem completed",
                    page,
                    listing_kind,
                )
                clamped = True
                break

            try:
                page_listings = extract_listings_from_search_page(body, listing_kind=listing_kind)
            except EmptyResultsError:
                logger.info(
                    "Página %s: fim da listagem (sem resultados) — kind=%s",
                    page,
                    listing_kind,
                )
                completed = True
                break
            except Exception as e:
                logger.exception("Erro ao extrair listings de %s: %s", url, e)
                if _fail(page_attempt):
                    break
                continue

            logger.info(
                "Página %s: %s listings extraídos (kind=%s ps=%s pe=%s)",
                page,
                len(page_listings),
                listing_kind,
                price_min,
                price_max,
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
            # while-else: loop ended without break.
            if not completed and page <= hard_cap:
                # Janela (PAGES_PER_INVOKE) esgotada — há mais páginas.
                next_page = page
            elif page > hard_cap:
                # Hard cap (SCRAPER_MAX_PAGES) — NÃO marcar completed.
                # completed=True dispara deactivate_missing_listings e apagaria
                # o corpus (ex.: smoke CI com MAX_PAGES=5). Só completed=True
                # quando o OLX realmente acaba (página vazia / sem ads novos).
                logger.warning(
                    "Parou no hard cap SCRAPER_MAX_PAGES=%s (próxima seria %s, kind=%s) "
                    "— sem completed/deactivate",
                    hard_cap,
                    page,
                    listing_kind,
                )
                next_page = None
    finally:
        _cycle_headers = None
        await close()

    listings = list(listings_by_id.values())
    logger.info(
        "Chunk kind=%s: %s listings | completed=%s | clamped=%s | next_page=%s | next_attempt=%s",
        listing_kind,
        len(listings),
        completed,
        clamped,
        next_page,
        next_attempt,
    )
    return SearchChunkResult(
        listings=listings,
        next_page=next_page,
        completed=completed,
        listing_kind=listing_kind,
        next_attempt=next_attempt,
        clamped=clamped,
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
