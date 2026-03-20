"""Tests for scraper URL building and OLX ID extraction."""
from scraper.olx_scraper import build_search_url, extract_olx_id_from_url


class TestBuildSearchUrl:
    def test_defaults(self):
        url = build_search_url({})
        assert url == (
            "https://www.olx.com.br/imoveis/venda/apartamentos/"
            "estado-al/alagoas/maceio"
        )

    def test_rent_house(self):
        url = build_search_url({"property_type": "house", "transaction": "rent"})
        assert "/aluguel/casas/" in url

    def test_page_param(self):
        url = build_search_url({}, page=3)
        assert "o=3" in url

    def test_page_1_no_param(self):
        url = build_search_url({}, page=1)
        assert "o=" not in url

    def test_price_range(self):
        url = build_search_url({"price_min": 100000, "price_max": 500000})
        assert "pe=100000-500000" in url

    def test_price_min_only(self):
        url = build_search_url({"price_min": 200000})
        assert "pe=200000-999999999" in url

    def test_price_max_only(self):
        url = build_search_url({"price_max": 300000})
        assert "pe=0-300000" in url

    def test_neighborhoods_query(self):
        url = build_search_url({"neighborhoods": ["Centro", "Farol"]})
        assert "q=Centro+Farol" in url

    def test_land_sale(self):
        url = build_search_url({"property_type": "land", "transaction": "sale"})
        assert "/venda/terrenos/" in url

    def test_commercial_rent(self):
        url = build_search_url({"property_type": "commercial", "transaction": "rent"})
        assert "/aluguel/comercio-e-industria/" in url

    def test_unknown_property_type_falls_back(self):
        url = build_search_url({"property_type": "unknown"})
        assert "/apartamentos/" in url

    def test_all_property_types_rent(self):
        """URL de aluguel sem filtro de tipo: /imoveis/aluguel/estado-al/..."""
        url = build_search_url({"property_type": "all", "transaction": "rent"})
        assert url == (
            "https://www.olx.com.br/imoveis/aluguel/"
            "estado-al/alagoas/maceio"
        )

    def test_all_property_types_sale(self):
        """URL de venda sem filtro de tipo: /imoveis/venda/estado-al/..."""
        url = build_search_url({"property_type": "all", "transaction": "sale"})
        assert url == (
            "https://www.olx.com.br/imoveis/venda/"
            "estado-al/alagoas/maceio"
        )

    def test_all_rent_with_sp(self):
        """URL de aluguel com parâmetro sp (sponsored position)."""
        url = build_search_url(
            {"property_type": "all", "transaction": "rent", "sp": 2}
        )
        assert url == (
            "https://www.olx.com.br/imoveis/aluguel/"
            "estado-al/alagoas/maceio?sp=2"
        )

    def test_all_with_price_and_page(self):
        url = build_search_url(
            {"property_type": "all", "transaction": "sale", "price_max": 500000},
            page=2,
        )
        assert "/imoveis/venda/estado-al/" in url
        assert "apartamentos" not in url
        assert "o=2" in url
        assert "pe=0-500000" in url

    def test_sp_param_preserved_with_type(self):
        url = build_search_url(
            {"property_type": "apartment", "transaction": "rent", "sp": 3}
        )
        assert "/aluguel/apartamentos/" in url
        assert "sp=3" in url


class TestExtractOlxId:
    def test_typical_url(self):
        assert extract_olx_id_from_url(
            "https://www.olx.com.br/d/imoveis/apartamento-123456789"
        ) is None  # no bare numeric segment with 8+ digits

    def test_url_with_id(self):
        assert (
            extract_olx_id_from_url(
                "https://www.olx.com.br/d/imoveis/12345678"
            )
            == "12345678"
        )

    def test_url_with_query(self):
        assert (
            extract_olx_id_from_url(
                "https://www.olx.com.br/d/imoveis/12345678?foo=bar"
            )
            == "12345678"
        )

    def test_short_id_rejected(self):
        assert extract_olx_id_from_url("https://olx.com.br/d/1234567") is None

    def test_no_id(self):
        assert extract_olx_id_from_url("https://olx.com.br/") is None
