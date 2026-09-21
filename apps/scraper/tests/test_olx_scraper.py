from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from collector import olx_scraper
from collector.olx_scraper import (
    EmptyResultsError,
    ParseError,
    _extract_ads_container_from_rsc,
    _is_empty_results_page,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _load_html(name: str) -> str:
    return (FIXTURES_DIR / name).read_text(encoding="utf-8")


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


def test_broken_page_without_empty_marker_raises_parse_error_and_dumps_debug(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)

    with pytest.raises(ParseError):
        _extract_ads_container_from_rsc(
            "<html><body><h1>Algum problema de parse</h1></body></html>"
        )

    assert (tmp_path / "debug_last_response.html").exists()


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
