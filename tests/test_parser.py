"""Tests for the HTML/JSON parser module."""
import json

from scraper.parser import _normalize_url, _parse_price, parse_listing_page, parse_search_page


class TestNormalizeUrl:
    def test_absolute(self):
        assert _normalize_url("https://www.olx.com.br/d/foo") == "https://www.olx.com.br/d/foo"

    def test_relative(self):
        assert _normalize_url("/d/foo") == "https://www.olx.com.br/d/foo"

    def test_strips_query(self):
        assert _normalize_url("/d/foo?bar=1") == "https://www.olx.com.br/d/foo"

    def test_strips_trailing_slash(self):
        assert _normalize_url("/d/foo/") == "https://www.olx.com.br/d/foo"


class TestParsePrice:
    def test_none(self):
        assert _parse_price(None) is None

    def test_int(self):
        assert _parse_price(350000) == 350000.0

    def test_float(self):
        assert _parse_price(199.99) == 199.99

    def test_brl_string(self):
        assert _parse_price("R$ 320.000") == 320000.0

    def test_empty_string(self):
        assert _parse_price("") is None

    def test_no_digits(self):
        assert _parse_price("abc") is None


class TestParseSearchPage:
    def _make_next_data_html(self, ads_data):
        """Helper: wrap ad dicts in a __NEXT_DATA__ script tag."""
        payload = {"props": {"pageProps": {"ads": ads_data}}}
        return (
            "<html><head>"
            f'<script id="__NEXT_DATA__" type="application/json">'
            f"{json.dumps(payload)}</script>"
            "</head><body></body></html>"
        )

    def test_empty_html(self):
        assert parse_search_page("<html><body></body></html>") == []

    def test_next_data_ads(self):
        ads = [
            {
                "listId": "12345678",
                "title": "Apto Centro",
                "priceValue": "R$ 250.000",
                "url": "/d/imoveis/apto-12345678",
            }
        ]
        result = parse_search_page(self._make_next_data_html(ads))
        assert len(result) == 1
        assert result[0]["olx_id"] == "12345678"
        assert result[0]["title"] == "Apto Centro"
        assert result[0]["price"] == 250000.0

    def test_deduplicates(self):
        ad = {
            "listId": "12345678",
            "title": "Apto",
            "priceValue": "100000",
            "url": "/d/imoveis/12345678",
        }
        result = parse_search_page(self._make_next_data_html([ad, ad]))
        assert len(result) == 1

    def test_fallback_to_anchor_links(self):
        html = """<html><body>
        <a href="/d/imoveis/apartamento/12345678">Apartamento</a>
        <a href="/d/imoveis/casa/87654321">Casa</a>
        </body></html>"""
        result = parse_search_page(html)
        assert len(result) == 2
        ids = {r["olx_id"] for r in result}
        assert ids == {"12345678", "87654321"}


class TestParseListingPage:
    def test_normal_listing(self):
        data = {
            "props": {
                "pageProps": {
                    "ad": {
                        "listId": "12345678",
                        "title": "Casa Bonita",
                        "priceValue": "450000",
                        "url": "/d/imoveis/12345678",
                    }
                }
            }
        }
        html = (
            "<html><head>"
            f'<script id="__NEXT_DATA__" type="application/json">'
            f"{json.dumps(data)}</script>"
            "</head><body><h1>Casa Bonita</h1></body></html>"
        )
        result = parse_listing_page(html)
        assert result["title"] == "Casa Bonita"
        assert result["price"] == 450000.0
        assert result["removed"] is False

    def test_removed_listing(self):
        html = "<html><body><p>Anúncio não encontrado</p></body></html>"
        result = parse_listing_page(html)
        assert result["removed"] is True

    def test_expired_listing(self):
        html = "<html><body><p>anúncio expirado</p></body></html>"
        result = parse_listing_page(html)
        assert result["removed"] is True
