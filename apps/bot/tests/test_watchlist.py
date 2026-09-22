"""Tests for watchlist toasts, Pro sell copy, and Stars payload helpers."""

from __future__ import annotations

from handlers.billing import _parse_pro_payload, _pro_invoice_payload
from handlers.ui import menus
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


def test_toast_for_create_status_email_trial(monkeypatch) -> None:
    monkeypatch.setattr("config.BILLING_ENABLED", False)
    monkeypatch.setattr("config.WATCHLIST_FREE_CAP", 2)
    monkeypatch.setattr("config.WATCHLIST_PRO_CAP", 10)
    created = _toast_for_create_status("created").lower()
    assert "adicionado" in created
    assert "preço" in created
    assert "já acompanha" in _toast_for_create_status("duplicate").lower()
    cap = _toast_for_create_status("cap_reached")
    assert "2" in cap
    assert "e-mail" in cap.lower()
    assert "radar pro" in cap.lower()
    assert "radar" in _toast_for_create_status("listing_missing").lower()


def test_toast_for_create_status_stars(monkeypatch) -> None:
    monkeypatch.setattr("config.BILLING_ENABLED", True)
    monkeypatch.setattr("config.WATCHLIST_FREE_CAP", 2)
    monkeypatch.setattr("config.WATCHLIST_PRO_CAP", 10)
    monkeypatch.setattr("config.PRO_STARS_AMOUNT", 200)
    monkeypatch.setattr("config.PRO_PRICE_BRL_LABEL", "R$ 19,90")
    cap = _toast_for_create_status("cap_reached")
    assert "2" in cap
    assert "Stars" in cap or "stars" in cap.lower()
    assert "19,90" in cap


def test_watchlist_cap_reached_email_trial(monkeypatch) -> None:
    monkeypatch.setattr("config.BILLING_ENABLED", False)
    monkeypatch.setattr("config.WATCHLIST_FREE_CAP", 2)
    monkeypatch.setattr("config.WATCHLIST_PRO_CAP", 10)
    monkeypatch.setattr("config.ALERT_PRO_CAP", 5)
    monkeypatch.setattr("config.EMAIL_PRO_TRIAL_DAYS", 30)
    text = menus.watchlist_cap_reached()
    assert "Radar Pro" in text
    assert "e-mail" in text.lower()
    assert "10" in text
    assert "Stars" not in text


def test_watchlist_cap_reached_sells_stars(monkeypatch) -> None:
    monkeypatch.setattr("config.BILLING_ENABLED", True)
    monkeypatch.setattr("config.WATCHLIST_FREE_CAP", 2)
    monkeypatch.setattr("config.WATCHLIST_PRO_CAP", 10)
    monkeypatch.setattr("config.ALERT_PRO_CAP", 5)
    monkeypatch.setattr("config.PRO_STARS_AMOUNT", 200)
    monkeypatch.setattr("config.PRO_PRICE_BRL_LABEL", "R$ 19,90")
    text = menus.watchlist_cap_reached()
    assert "Radar Pro" in text
    assert "200 Stars" in text
    assert "19,90" in text
    assert "10" in text


def test_pro_invoice_payload_roundtrip() -> None:
    assert _pro_invoice_payload(42) == "pro_monthly:42"
    assert _parse_pro_payload("pro_monthly:42") == 42
    assert _parse_pro_payload("other") is None
