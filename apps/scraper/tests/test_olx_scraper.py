from __future__ import annotations

import asyncio
import gzip
from pathlib import Path
from typing import Any

import pytest
from curl_cffi.requests.exceptions import RequestException

from collector import olx_scraper
from collector.olx_scraper import (
    EmptyResultsError,
    FetchError,
    ParseError,
    TransientFetchError,
    _extract_ads_candidates,
    _extract_ads_container_from_rsc,
    _extract_rsc_payload,
    _is_empty_results_page,
    _is_flight,
    _listings_url,
    is_clamped_page,
    returned_page_number,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _load_html(name: str) -> str:
    return (FIXTURES_DIR / name).read_text(encoding="utf-8")


def _load_flight(name: str) -> str:
    """Flight cru (`text/x-component`) capturado da OLX, versionado gzipado."""
    with gzip.open(FIXTURES_DIR / name, "rt", encoding="utf-8") as fh:
        return fh.read()


def test_is_empty_results_page_true_on_empty_state() -> None:
    html = _load_html("empty_results_page.html")
    assert _is_empty_results_page(html) is True


def test_is_empty_results_page_false_on_regular_html() -> None:
    html = "<html><body><h1>Com resultados</h1></body></html>"
    assert _is_empty_results_page(html) is False


def test_empty_results_page_raises_empty_result_error_without_debug_file(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)

    with pytest.raises(EmptyResultsError):
        _extract_ads_container_from_rsc(_load_html("empty_results_page.html"))

    assert not (tmp_path / "debug_last_response.html").exists()


def test_broken_page_raises_parse_error_without_cwd_dump(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    dest = tmp_path / "dump" / "debug_last_response.html"
    dest.parent.mkdir()
    monkeypatch.setattr(olx_scraper, "DEBUG_HTML_PATH", dest)

    with pytest.raises(ParseError):
        _extract_ads_container_from_rsc(
            "<html><body><h1>Algum problema de parse</h1></body></html>"
        )

    assert not (tmp_path / "debug_last_response.html").exists()
    assert dest.is_file()


def test_debug_dump_oserror_still_raises_parse_error(monkeypatch) -> None:
    class _ReadOnly:
        def write_text(self, *_args, **_kwargs) -> None:
            raise OSError(30, "Read-only file system")

        def __str__(self) -> str:
            return "/tmp/debug_last_response.html"

    monkeypatch.setattr(olx_scraper, "DEBUG_HTML_PATH", _ReadOnly())

    with pytest.raises(ParseError):
        _extract_ads_container_from_rsc(
            "<html><body><h1>Algum problema de parse</h1></body></html>"
        )


# --- Flight cru (text/x-component) ------------------------------------------
# Capturado em 28 set 2026, `impersonate="chrome150"` + `RSC: 1`:
#   olx_search_page_flight: .../alagoas/maceio?sf=1              (50 anúncios)
#   olx_empty_page_flight:  .../alagoas/maceio?sf=1&o=100        (fim da listagem)
# Versionados gzipados (~31 KB + ~13 KB) para manter o payload real no repo.
SEARCH_FLIGHT = "olx_search_page_flight.txt.gz"
EMPTY_FLIGHT = "olx_empty_page_flight.txt.gz"


def test_extract_rsc_payload_passes_flight_through() -> None:
    flight = '1a:["$","$L1",null,{"ads":[]}]\n2b:["$","$L2",null,{}]\n'

    assert _is_flight(flight) is True
    assert _extract_rsc_payload(flight) == flight


def test_extract_rsc_payload_still_reads_html_chunks() -> None:
    html = (
        '<html><script>self.__next_f.push([1,"a"])</script>'
        '<script>self.__next_f.push([1,"b"])</script></html>'
    )

    assert _is_flight(html) is False
    assert _extract_rsc_payload(html) == "ab"


def test_flight_search_page_yields_50_listings() -> None:
    flight = _load_flight(SEARCH_FLIGHT)

    listings = olx_scraper.extract_listings_from_search_page(flight, listing_kind="aluguel")

    assert len(listings) == 50
    assert len({ad["listing_id"] for ad in listings}) == 50
    assert all(ad["listing_kind"] == "aluguel" for ad in listings)
    # Página 1 não informa número no título.
    assert returned_page_number(flight) is None
    assert is_clamped_page(flight, 1) is False


def test_flight_has_a_decoy_empty_ads_array() -> None:
    """A página traz um `"ads":[]` de outro componente antes do array real."""
    flight = _load_flight(SEARCH_FLIGHT)
    candidates = _extract_ads_candidates(flight)

    assert len(candidates) > 1
    assert any(len(candidate) == 0 for candidate in candidates)
    assert _extract_ads_container_from_rsc(flight)["ads"] == max(candidates, key=len)


def test_flight_empty_page_is_end_of_listing() -> None:
    flight = _load_flight(EMPTY_FLIGHT)

    assert _is_empty_results_page(flight) is True
    with pytest.raises(EmptyResultsError):
        olx_scraper.extract_listings_from_search_page(flight)


def test_flight_empty_page_reports_page_100_and_clamps_only_above_it() -> None:
    flight = _load_flight(EMPTY_FLIGHT)

    assert returned_page_number(flight) == 100
    assert is_clamped_page(flight, 100) is False  # fim real da listagem
    assert is_clamped_page(flight, 101) is True  # teto de paginação da OLX
    assert is_clamped_page(flight, 1) is False


def test_html_page_still_reports_page_number_from_title() -> None:
    html = (
        "<html><head><title>Imóveis à venda - Recife, PE - Página 100 | OLX"
        "</title></head></html>"
    )

    assert _is_flight(html) is False
    assert returned_page_number(html) == 100
    assert is_clamped_page(html, 101) is True


def test_flight_without_ads_array_dumps_body_and_raises_parse_error(
    tmp_path, monkeypatch
) -> None:
    dest = tmp_path / "debug_last_response.html"
    monkeypatch.setattr(olx_scraper, "DEBUG_HTML_PATH", dest)
    flight = '1a:["$","$L1",null,{"fullPageTitle":"Imóveis - Maceió | OLX"}]\n'

    with pytest.raises(ParseError):
        _extract_ads_container_from_rsc(flight)

    assert dest.read_text(encoding="utf-8") == flight


def test_flight_ads_without_list_id_is_parse_error_not_end_of_listing(
    tmp_path, monkeypatch
) -> None:
    """`ads` presente mas sem `listId` é quebra de layout — não fim de listagem."""
    monkeypatch.setattr(olx_scraper, "DEBUG_HTML_PATH", tmp_path / "dump.html")
    flight = '2b:["$","$L21",null,{"ads":[{"subject":"sem id"}]}]\n'

    assert _is_empty_results_page(flight) is False
    with pytest.raises(ParseError):
        _extract_ads_container_from_rsc(flight)


def test_search_all_stops_cleanly_on_empty_page(monkeypatch) -> None:
    calls: list[str] = []

    async def fake_fetch(url: str, headers=None) -> str:
        calls.append(url)
        return _load_html("empty_results_page.html")

    async def fake_close() -> None:
        return None

    def raise_empty(*args, **kwargs):
        raise EmptyResultsError("fim da listagem")

    monkeypatch.setattr(olx_scraper, "fetch", fake_fetch)
    monkeypatch.setattr(olx_scraper, "close", fake_close)
    monkeypatch.setattr(olx_scraper, "extract_listings_from_search_page", raise_empty)

    result = asyncio.run(olx_scraper.search_all_rent_maceio())

    assert result == []
    assert len(calls) == 1


def test_search_listings_window_sets_next_page(monkeypatch) -> None:
    page_calls: list[str] = []

    async def fake_fetch(url: str, headers=None) -> str:
        page_calls.append(url)
        return "<html></html>"

    async def fake_close() -> None:
        return None

    def fake_extract(html: str, *, listing_kind="aluguel"):
        # Um listing único por chamada, com id crescente via len(page_calls)
        n = len(page_calls)
        return [
            {
                "listing_id": n,
                "url": f"https://ex/{n}",
                "title": f"t{n}",
                "price_value": 100,
                "old_price": None,
                "municipality": "Maceió",
                "neighbourhood": "Centro",
                "properties": {},
                "category": "Casas",
                "images": ["https://img/x.webp"],
                "listing_kind": listing_kind,
            }
        ]

    monkeypatch.setattr(olx_scraper, "fetch", fake_fetch)
    monkeypatch.setattr(olx_scraper, "close", fake_close)
    monkeypatch.setattr(olx_scraper, "extract_listings_from_search_page", fake_extract)
    monkeypatch.setattr(olx_scraper.config, "SCRAPER_PAGES_PER_INVOKE", 2)
    monkeypatch.setattr(olx_scraper.config, "SCRAPER_MAX_PAGES", 100)

    chunk = asyncio.run(
        olx_scraper.search_listings(
            "https://www.olx.com.br/imoveis/venda/estado-al/alagoas/maceio",
            listing_kind="venda",
            start_page=1,
            max_pages=2,
        )
    )

    assert chunk.completed is False
    assert chunk.next_page == 3
    assert chunk.listing_kind == "venda"
    assert len(chunk.listings) == 2
    assert all(ad["listing_kind"] == "venda" for ad in chunk.listings)
    assert page_calls[0].endswith("/maceio?sf=1")
    assert page_calls[1].endswith("/maceio?sf=1&o=2")


def test_search_listings_hard_cap_does_not_mark_completed(monkeypatch) -> None:
    """SCRAPER_MAX_PAGES não pode setar completed=True (evita mass-deactivate)."""
    page_calls: list[str] = []

    async def fake_fetch(url: str, headers=None) -> str:
        page_calls.append(url)
        return "<html></html>"

    async def fake_close() -> None:
        return None

    def fake_extract(html: str, *, listing_kind="aluguel"):
        n = len(page_calls)
        return [
            {
                "listing_id": n,
                "url": f"https://ex/{n}",
                "title": f"t{n}",
                "price_value": 100,
                "old_price": None,
                "municipality": "Maceió",
                "neighbourhood": "Centro",
                "properties": {},
                "category": "Casas",
                "images": ["https://img/x.webp"],
                "listing_kind": listing_kind,
            }
        ]

    monkeypatch.setattr(olx_scraper, "fetch", fake_fetch)
    monkeypatch.setattr(olx_scraper, "close", fake_close)
    monkeypatch.setattr(olx_scraper, "extract_listings_from_search_page", fake_extract)
    monkeypatch.setattr(olx_scraper.config, "SCRAPER_PAGES_PER_INVOKE", 50)
    monkeypatch.setattr(olx_scraper.config, "SCRAPER_MAX_PAGES", 5)

    chunk = asyncio.run(
        olx_scraper.search_listings(
            "https://www.olx.com.br/imoveis/aluguel/estado-al/alagoas/maceio",
            listing_kind="aluguel",
            start_page=1,
        )
    )

    assert len(page_calls) == 5
    assert chunk.completed is False
    assert chunk.next_page is None
    assert len(chunk.listings) == 5


_SALE = "https://www.olx.com.br/imoveis/venda/estado-al/alagoas/maceio"
_RENT = "https://www.olx.com.br/imoveis/aluguel/estado-al/alagoas/maceio"


def test_listings_url_sorts_by_recent_and_keeps_page_query() -> None:
    assert _listings_url(_RENT, 1) == f"{_RENT}?sf=1"
    assert _listings_url(_RENT, 2) == f"{_RENT}?sf=1&o=2"
    # Base que já tem query não pode virar "?sf=1?o=2".
    assert _listings_url(f"{_RENT}?sf=1", 2) == f"{_RENT}?sf=1&o=2"


_RECIFE_SALE = "https://www.olx.com.br/imoveis/venda/estado-pe/grande-recife/recife"
_NATAL_SALE = "https://www.olx.com.br/imoveis/venda/estado-rn/rio-grande-do-norte/natal"
_NATAL_RENT = "https://www.olx.com.br/imoveis/aluguel/estado-rn/rio-grande-do-norte/natal"


def test_listings_url_recife_keeps_recent_sort() -> None:
    assert _listings_url(_RECIFE_SALE, 1) == f"{_RECIFE_SALE}?sf=1"
    assert (
        _listings_url(_RECIFE_SALE, 2, price_min=300_000, price_max=350_000)
        == f"{_RECIFE_SALE}?sf=1&ps=300000&pe=350000&o=2"
    )


def test_listings_url_natal_keeps_recent_sort() -> None:
    assert _listings_url(_NATAL_RENT, 1) == f"{_NATAL_RENT}?sf=1"
    assert _listings_url(_NATAL_RENT, 2) == f"{_NATAL_RENT}?sf=1&o=2"
    assert _listings_url(_NATAL_SALE, 1) == f"{_NATAL_SALE}?sf=1"
    assert (
        _listings_url(_NATAL_SALE, 2, price_min=300_000, price_max=500_000)
        == f"{_NATAL_SALE}?sf=1&ps=300000&pe=500000&o=2"
    )


def test_search_listings_clamp_does_not_complete(monkeypatch) -> None:
    async def fake_fetch(url: str, headers=None) -> str:
        del url, headers
        return (
            "<html><head><title>"
            "Imóveis à venda - Recife, PE - Página 100 | OLX"
            "</title></head><body></body></html>"
        )

    async def fake_close() -> None:
        return None

    def explode(html: str, *, listing_kind: str = "aluguel"):
        del html, listing_kind
        raise AssertionError("página clampada não deve ser extraída")

    monkeypatch.setattr(olx_scraper, "fetch", fake_fetch)
    monkeypatch.setattr(olx_scraper, "close", fake_close)
    monkeypatch.setattr(olx_scraper, "extract_listings_from_search_page", explode)

    chunk = asyncio.run(
        olx_scraper.search_listings(
            _RECIFE_SALE,
            listing_kind="venda",
            start_page=101,
            max_pages=2,
        )
    )

    assert chunk.completed is False
    assert chunk.clamped is True
    assert chunk.next_page is None
    assert chunk.listings == []


def test_listings_url_price_slice() -> None:
    assert _listings_url(_SALE, 1, price_max=300_000) == f"{_SALE}?sf=1&pe=300000"
    assert (
        _listings_url(_SALE, 2, price_min=500_000, price_max=700_000)
        == f"{_SALE}?sf=1&ps=500000&pe=700000&o=2"
    )
    assert _listings_url(_SALE, 3, price_min=1_000_000) == f"{_SALE}?sf=1&ps=1000000&o=3"


def test_fetch_retries_retryable_status(monkeypatch) -> None:
    calls = {"n": 0}

    def fake_sync(url: str, headers: dict) -> tuple[int, str]:
        calls["n"] += 1
        if calls["n"] < 3:
            return 403, ""
        return 200, "ok"

    async def no_wait(*_args, **_kwargs) -> None:
        return None

    monkeypatch.setattr(olx_scraper, "_sync_get", fake_sync)
    monkeypatch.setattr(olx_scraper, "_delay", no_wait)
    monkeypatch.setattr(olx_scraper.asyncio, "sleep", no_wait)
    monkeypatch.setattr(olx_scraper.config, "SCRAPER_FETCH_RETRIES", 3)

    html = asyncio.run(olx_scraper.fetch("https://example.test/list"))

    assert html == "ok"
    assert calls["n"] == 3


def _patch_fetch_sleep(monkeypatch) -> None:
    """Remove o delay real entre tentativas e fixa o número de retries."""

    async def no_wait(*_args, **_kwargs) -> None:
        return None

    monkeypatch.setattr(olx_scraper, "_delay", no_wait)
    monkeypatch.setattr(olx_scraper.asyncio, "sleep", no_wait)
    monkeypatch.setattr(olx_scraper.config, "SCRAPER_FETCH_RETRIES", 3)


def test_build_headers_defers_to_fingerprint_and_asks_for_rsc() -> None:
    """UA/Accept-Language/Sec-Fetch vêm do impersonate; só o flight é explícito."""
    headers = olx_scraper._build_headers()

    assert headers["RSC"] == "1"
    assert headers["Accept"] == "text/x-component"
    assert headers["Referer"] == olx_scraper.config.OLX_REFERER
    assert "User-Agent" not in headers
    assert "Accept-Language" not in headers
    assert "Accept-Encoding" not in headers
    assert "Sec-Fetch-Mode" not in headers


def test_impersonate_preset_is_pinned() -> None:
    assert olx_scraper.IMPERSONATE == "chrome150"


def test_looks_like_challenge_matches_cloudflare_page() -> None:
    assert olx_scraper._looks_like_challenge("<title>Just a moment...</title>") is True
    assert olx_scraper._looks_like_challenge("<div id='cf-chl-widget'>") is True
    assert olx_scraper._looks_like_challenge("<html><h1>Imóveis</h1></html>") is False


def test_fetch_retries_transient_network_error(monkeypatch) -> None:
    calls = {"n": 0}

    def fake_sync(url: str, headers: dict) -> tuple[int, str]:
        del url, headers
        calls["n"] += 1
        if calls["n"] < 3:
            raise TransientFetchError("falha de rede")
        return 200, "ok"

    monkeypatch.setattr(olx_scraper, "_sync_get", fake_sync)
    _patch_fetch_sleep(monkeypatch)

    html = asyncio.run(olx_scraper.fetch("https://example.test/list"))

    assert html == "ok"
    assert calls["n"] == 3


def test_fetch_raises_fetch_error_when_network_error_persists(monkeypatch) -> None:
    def fake_sync(url: str, headers: dict) -> tuple[int, str]:
        del url, headers
        raise TransientFetchError("falha de rede")

    monkeypatch.setattr(olx_scraper, "_sync_get", fake_sync)
    _patch_fetch_sleep(monkeypatch)

    with pytest.raises(FetchError) as excinfo:
        asyncio.run(olx_scraper.fetch("https://example.test/list"))

    assert excinfo.value.status_code == 0


def test_fetch_retries_challenge_body_returned_with_http_200(monkeypatch) -> None:
    calls = {"n": 0}

    def fake_sync(url: str, headers: dict) -> tuple[int, str]:
        del url, headers
        calls["n"] += 1
        if calls["n"] < 3:
            return 200, "<html><title>Just a moment...</title></html>"
        return 200, "ok"

    monkeypatch.setattr(olx_scraper, "_sync_get", fake_sync)
    _patch_fetch_sleep(monkeypatch)

    html = asyncio.run(olx_scraper.fetch("https://example.test/list"))

    assert html == "ok"
    assert calls["n"] == 3


def test_fetch_exhausted_challenge_body_never_reaches_parser(monkeypatch) -> None:
    def fake_sync(url: str, headers: dict) -> tuple[int, str]:
        del url, headers
        return 200, "<html><title>Just a moment...</title></html>"

    monkeypatch.setattr(olx_scraper, "_sync_get", fake_sync)
    _patch_fetch_sleep(monkeypatch)

    with pytest.raises(FetchError) as excinfo:
        asyncio.run(olx_scraper.fetch("https://example.test/list"))

    assert excinfo.value.status_code == 0


def test_fetch_does_not_retry_not_found(monkeypatch) -> None:
    calls = {"n": 0}

    def fake_sync(url: str, headers: dict) -> tuple[int, str]:
        del url, headers
        calls["n"] += 1
        return 404, "nope"

    monkeypatch.setattr(olx_scraper, "_sync_get", fake_sync)
    _patch_fetch_sleep(monkeypatch)

    with pytest.raises(FetchError) as excinfo:
        asyncio.run(olx_scraper.fetch("https://example.test/list"))

    assert excinfo.value.status_code == 404
    assert calls["n"] == 1


def test_search_listings_style_session_is_reopened_after_close(monkeypatch) -> None:
    """`close()` encerra a Session e a coleta seguinte precisa reabrir uma nova.

    curl_cffi recusa reuso de Session fechada (`SessionClosed`); sem reabrir, a
    segunda coleta no mesmo processo (container quente da Lambda) falharia.
    """
    created: list[object] = []

    class _FakeSession:
        def __init__(self, **kwargs) -> None:
            self.kwargs = kwargs
            self.closed = False
            created.append(self)

        def get(self, *_args, **_kwargs):
            raise AssertionError("não deve ser chamado neste teste")

        def close(self) -> None:
            self.closed = True

    monkeypatch.setattr(olx_scraper, "Session", _FakeSession)
    monkeypatch.setattr(olx_scraper, "_http", None)

    first: Any = olx_scraper._get_session()
    assert first is olx_scraper._get_session()  # reaproveita a mesma sessão
    assert olx_scraper._get_session().kwargs["impersonate"] == olx_scraper.IMPERSONATE

    asyncio.run(olx_scraper.close())
    assert first.closed is True

    second: Any = olx_scraper._get_session()
    assert second is not first
    assert len(created) == 2


def test_sync_get_wraps_network_error_as_transient(monkeypatch) -> None:
    class _BrokenSession:
        def get(self, *_args, **_kwargs):
            raise RequestException("curl: (7) Failed to connect")

    monkeypatch.setattr(olx_scraper, "_http", _BrokenSession())

    with pytest.raises(TransientFetchError):
        olx_scraper._sync_get("https://example.test/list", {})


def _listing(n: int, kind: str = "aluguel") -> dict:
    return {
        "listing_id": n,
        "url": f"https://ex/{n}",
        "title": f"t{n}",
        "price_value": 100,
        "old_price": None,
        "municipality": "Maceió",
        "neighbourhood": "Centro",
        "properties": {},
        "category": "Casas",
        "images": ["https://img/x.webp"],
        "listing_kind": kind,
    }


def test_search_listings_requeues_page_before_max_attempts(monkeypatch) -> None:
    async def fake_fetch(url: str, headers=None) -> str:
        raise FetchError(403, url)

    async def fake_close() -> None:
        return None

    monkeypatch.setattr(olx_scraper, "fetch", fake_fetch)
    monkeypatch.setattr(olx_scraper, "close", fake_close)
    monkeypatch.setattr(olx_scraper.config, "SCRAPER_PAGE_MAX_ATTEMPTS", 3)

    chunk = asyncio.run(
        olx_scraper.search_listings(
            _RENT,
            listing_kind="aluguel",
            start_page=4,
            attempt=0,
        )
    )

    assert chunk.completed is False
    assert chunk.next_page == 4
    assert chunk.next_attempt == 1
    assert chunk.listings == []


def test_search_listings_skips_page_after_max_attempts(monkeypatch) -> None:
    fetched: list[str] = []

    async def fake_fetch(url: str, headers=None) -> str:
        fetched.append(url)
        if "o=5" in url:
            raise FetchError(502, url)
        return "<html></html>"

    async def fake_close() -> None:
        return None

    def fake_extract(html: str, *, listing_kind: str = "aluguel"):
        return [_listing(len(fetched), listing_kind)]

    monkeypatch.setattr(olx_scraper, "fetch", fake_fetch)
    monkeypatch.setattr(olx_scraper, "close", fake_close)
    monkeypatch.setattr(olx_scraper, "extract_listings_from_search_page", fake_extract)
    monkeypatch.setattr(olx_scraper.config, "SCRAPER_PAGE_MAX_ATTEMPTS", 3)
    monkeypatch.setattr(olx_scraper.config, "SCRAPER_MAX_PAGES", 20)

    chunk = asyncio.run(
        olx_scraper.search_listings(
            _RENT,
            listing_kind="aluguel",
            start_page=5,
            attempt=2,
            max_pages=1,
        )
    )

    assert any("o=5" in url for url in fetched)
    assert any("o=6" in url for url in fetched)
    assert chunk.completed is False
    assert chunk.next_page == 7
    assert chunk.next_attempt == 0
    assert len(chunk.listings) == 1
