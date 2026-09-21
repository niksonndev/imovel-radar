"""Tests for watchlist URL parsing and create-status toasts."""

from __future__ import annotations

from handlers.watchlist import _toast_for_create_status, parse_olx_listing_id


def test_parse_olx_listing_id_from_url() -> None:
    url = "https://al.olx.com.br/alagoas/imoveis/casa-para-alugar-condominio-1525220692"
    assert parse_olx_listing_id(url) == 1525220692


def test_parse_olx_listing_id_with_query_and_trailing_slash() -> None:
    url = "https://al.olx.com.br/alagoas/imoveis/apto-1537459281/?foo=1"
    assert parse_olx_listing_id(url) == 1537459281


def test_parse_olx_listing_id_bare_digits() -> None:
    assert parse_olx_listing_id("1525220692") == 1525220692
    assert parse_olx_listing_id(" 1525220692 ") == 1525220692


def test_parse_olx_listing_id_invalid() -> None:
    assert parse_olx_listing_id("") is None
    assert parse_olx_listing_id("https://olx.com.br/imoveis") is None
    assert parse_olx_listing_id("123") is None  # too short


def test_toast_for_create_status(monkeypatch) -> None:
    monkeypatch.setattr("config.WATCHLIST_FREE_CAP", 2)
    assert "adicionado" in _toast_for_create_status("created").lower()
    assert "já acompanha" in _toast_for_create_status("duplicate").lower()
    assert "2" in _toast_for_create_status("cap_reached")
    assert "radar" in _toast_for_create_status("listing_missing").lower()
