"""Testes de integração: valida o fluxo completo de scraping (URL → fetch → parse → filtros)
usando HTML mockado para não depender de rede."""
import json
from unittest.mock import AsyncMock, patch

import pytest

from scraper.olx_scraper import OLXScraper, build_search_url

pytestmark = pytest.mark.asyncio


def _make_next_data_html(ads_data):
    payload = {"props": {"pageProps": {"ads": ads_data}}}
    return (
        "<html><head>"
        f'<script id="__NEXT_DATA__" type="application/json">'
        f"{json.dumps(payload)}</script>"
        "</head><body></body></html>"
    )


SAMPLE_ADS = [
    {
        "listId": "11111111",
        "title": "Apartamento Centro 2 quartos",
        "priceValue": "R$ 250.000",
        "url": "/d/imoveis/apto-11111111",
        "locationDetails": {"neighbourhood": "Centro"},
        "properties": [
            {"name": "Quartos", "value": "2"},
            {"name": "Área útil", "value": "65 m²"},
        ],
    },
    {
        "listId": "22222222",
        "title": "Casa Farol 3 quartos",
        "priceValue": "R$ 450.000",
        "url": "/d/imoveis/casa-22222222",
        "locationDetails": {"neighbourhood": "Farol"},
        "properties": [
            {"name": "Quartos", "value": "3"},
            {"name": "Área útil", "value": "120 m²"},
        ],
    },
    {
        "listId": "33333333",
        "title": "Terreno Jatiúca",
        "priceValue": "R$ 180.000",
        "url": "/d/imoveis/terreno-33333333",
        "locationDetails": {"neighbourhood": "Jatiúca"},
        "properties": [],
    },
    {
        "listId": "44444444",
        "title": "Sala Comercial Pajuçara",
        "priceValue": "R$ 1.500",
        "url": "/d/imoveis/sala-44444444",
        "locationDetails": {"neighbourhood": "Pajuçara"},
        "properties": [
            {"name": "Área útil", "value": "40 m²"},
        ],
    },
]


class TestScrapingIntegrationRent:
    """Testa o fluxo de scraping para aluguel (todos os tipos)."""

    async def test_rent_all_url_matches(self):
        url = build_search_url({"property_type": "all", "transaction": "rent"})
        assert url == "https://www.olx.com.br/imoveis/aluguel/estado-al/alagoas/maceio"

    async def test_rent_all_with_sp(self):
        url = build_search_url({"property_type": "all", "transaction": "rent", "sp": 2})
        assert url == "https://www.olx.com.br/imoveis/aluguel/estado-al/alagoas/maceio?sp=2"

    async def test_rent_search_listings_returns_all_types(self):
        scraper = OLXScraper()
        html = _make_next_data_html(SAMPLE_ADS)
        scraper.fetch = AsyncMock(return_value=html)

        filters = {"property_type": "all", "transaction": "rent"}
        ads = await scraper.search_listings(filters, max_pages=1)
        assert len(ads) == 4
        ids = {ad["olx_id"] for ad in ads}
        assert ids == {"11111111", "22222222", "33333333", "44444444"}

    async def test_rent_search_with_neighborhood_filter(self):
        scraper = OLXScraper()
        html = _make_next_data_html(SAMPLE_ADS)
        scraper.fetch = AsyncMock(return_value=html)

        filters = {
            "property_type": "all",
            "transaction": "rent",
            "neighborhoods": ["Centro", "Farol"],
        }
        ads = await scraper.search_listings(filters, max_pages=1)
        assert len(ads) == 2
        ids = {ad["olx_id"] for ad in ads}
        assert ids == {"11111111", "22222222"}

    async def test_rent_search_with_bedrooms_filter(self):
        scraper = OLXScraper()
        html = _make_next_data_html(SAMPLE_ADS)
        scraper.fetch = AsyncMock(return_value=html)

        filters = {"property_type": "all", "transaction": "rent", "bedrooms_min": 3}
        ads = await scraper.search_listings(filters, max_pages=1)
        bedrooms_ads = [a for a in ads if a.get("bedrooms") is not None]
        for ad in bedrooms_ads:
            assert ad["bedrooms"] >= 3


class TestScrapingIntegrationSale:
    """Testa o fluxo de scraping para venda (todos os tipos)."""

    async def test_sale_all_url_matches(self):
        url = build_search_url({"property_type": "all", "transaction": "sale"})
        assert url == "https://www.olx.com.br/imoveis/venda/estado-al/alagoas/maceio"

    async def test_sale_search_listings_returns_all(self):
        scraper = OLXScraper()
        html = _make_next_data_html(SAMPLE_ADS)
        scraper.fetch = AsyncMock(return_value=html)

        filters = {"property_type": "all", "transaction": "sale"}
        ads = await scraper.search_listings(filters, max_pages=1)
        assert len(ads) == 4

    async def test_sale_search_with_price_filter(self):
        scraper = OLXScraper()
        html = _make_next_data_html(SAMPLE_ADS)
        scraper.fetch = AsyncMock(return_value=html)

        filters = {
            "property_type": "all",
            "transaction": "sale",
            "price_min": 200000,
            "price_max": 500000,
        }
        url = build_search_url(filters)
        assert "ps=200000" in url
        assert "pe=500000" in url

        ads = await scraper.search_listings(filters, max_pages=1)
        assert len(ads) == 4

    async def test_sale_search_with_area_filter(self):
        scraper = OLXScraper()
        html = _make_next_data_html(SAMPLE_ADS)
        scraper.fetch = AsyncMock(return_value=html)

        filters = {"property_type": "all", "transaction": "sale", "area_min": 50, "area_max": 100}
        ads = await scraper.search_listings(filters, max_pages=1)
        area_ads = [a for a in ads if a.get("area_m2") is not None]
        for ad in area_ads:
            assert 50 <= ad["area_m2"] <= 100


class TestScrapingMultipage:
    """Valida paginação no scraping com property_type='all'."""

    async def test_multipages_dedup(self):
        page1_ads = [
            {
                "listId": str(10000000 + i),
                "title": f"Imóvel {i}",
                "priceValue": str(100000 + i * 1000),
                "url": f"/d/imoveis/{10000000 + i}",
            }
            for i in range(20)
        ]
        page2_ads = SAMPLE_ADS[:2]
        page1_html = _make_next_data_html(page1_ads)
        page2_html = _make_next_data_html(page2_ads)

        scraper = OLXScraper()
        call_count = 0

        async def mock_fetch(url):
            nonlocal call_count
            call_count += 1
            if "o=2" in url:
                return page2_html
            return page1_html

        scraper.fetch = AsyncMock(side_effect=mock_fetch)

        filters = {"property_type": "all", "transaction": "rent"}
        ads = await scraper.search_listings(filters, max_pages=2)
        assert len(ads) == 22
        assert call_count == 2

    async def test_url_pattern_per_page(self):
        """Verifica que a URL de cada página está correta."""
        scraper = OLXScraper()
        scraper.fetch = AsyncMock(return_value=_make_next_data_html([]))

        filters = {"property_type": "all", "transaction": "rent", "sp": 2}
        await scraper.search_listings(filters, max_pages=1)

        called_url = scraper.fetch.call_args[0][0]
        assert called_url == "https://www.olx.com.br/imoveis/aluguel/estado-al/alagoas/maceio?sp=2"


class TestBackwardsCompatibility:
    """Garante que alertas existentes (com property_type específico) continuam funcionando."""

    async def test_apartment_sale_unchanged(self):
        url = build_search_url({"property_type": "apartment", "transaction": "sale"})
        assert "/imoveis/venda/apartamentos/estado-al/alagoas/maceio" in url

    async def test_house_rent_unchanged(self):
        url = build_search_url({"property_type": "house", "transaction": "rent"})
        assert "/imoveis/aluguel/casas/estado-al/alagoas/maceio" in url

    async def test_default_is_all_types(self):
        url = build_search_url({})
        assert url == "https://www.olx.com.br/imoveis/venda/estado-al/alagoas/maceio"

    async def test_existing_scraping_with_specific_type(self):
        scraper = OLXScraper()
        html = _make_next_data_html(SAMPLE_ADS[:1])
        scraper.fetch = AsyncMock(return_value=html)

        filters = {"property_type": "apartment", "transaction": "sale"}
        ads = await scraper.search_listings(filters, max_pages=1)
        assert len(ads) == 1

        called_url = scraper.fetch.call_args[0][0]
        assert "/apartamentos/" in called_url
