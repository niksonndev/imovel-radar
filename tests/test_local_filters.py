"""Tests for the local post-scrape filtering logic in OLXScraper."""
from scraper.olx_scraper import OLXScraper


def _make_ad(**kwargs):
    base = {
        "olx_id": "1",
        "title": "Imóvel",
        "price": 200000,
        "url": "https://olx.com.br/d/1",
        "thumbnail": None,
        "neighborhood": "",
        "bedrooms": None,
        "area_m2": None,
    }
    base.update(kwargs)
    return base


class TestApplyLocalFilters:
    def setup_method(self):
        self.scraper = OLXScraper()

    def test_no_filters(self):
        ads = [_make_ad()]
        assert self.scraper._apply_local_filters(ads, {}) == ads

    def test_bedrooms_min_filters(self):
        ads = [
            _make_ad(olx_id="1", bedrooms=2),
            _make_ad(olx_id="2", bedrooms=3),
            _make_ad(olx_id="3", bedrooms=None),
        ]
        result = self.scraper._apply_local_filters(ads, {"bedrooms_min": 3})
        assert len(result) == 2
        ids = {a["olx_id"] for a in result}
        assert "1" not in ids
        assert "2" in ids
        assert "3" in ids  # None bedrooms are not filtered out

    def test_area_min(self):
        ads = [
            _make_ad(olx_id="1", area_m2=50),
            _make_ad(olx_id="2", area_m2=100),
        ]
        result = self.scraper._apply_local_filters(ads, {"area_min": 80})
        assert len(result) == 1
        assert result[0]["olx_id"] == "2"

    def test_area_max(self):
        ads = [
            _make_ad(olx_id="1", area_m2=50),
            _make_ad(olx_id="2", area_m2=200),
        ]
        result = self.scraper._apply_local_filters(ads, {"area_max": 100})
        assert len(result) == 1
        assert result[0]["olx_id"] == "1"

    def test_neighborhood_filter(self):
        ads = [
            _make_ad(olx_id="1", title="Apto Centro", neighborhood="Centro"),
            _make_ad(olx_id="2", title="Casa Farol", neighborhood="Farol"),
            _make_ad(olx_id="3", title="Terreno", neighborhood="Jatiúca"),
        ]
        result = self.scraper._apply_local_filters(
            ads, {"neighborhoods": ["Centro"]}
        )
        assert len(result) == 1
        assert result[0]["olx_id"] == "1"

    def test_neighborhood_case_insensitive(self):
        ads = [_make_ad(title="Apto em CENTRO", neighborhood="")]
        result = self.scraper._apply_local_filters(
            ads, {"neighborhoods": ["centro"]}
        )
        assert len(result) == 1

    def test_combined_filters(self):
        ads = [
            _make_ad(olx_id="1", bedrooms=3, area_m2=80, neighborhood="Centro"),
            _make_ad(olx_id="2", bedrooms=1, area_m2=120, neighborhood="Centro"),
            _make_ad(olx_id="3", bedrooms=3, area_m2=120, neighborhood="Farol"),
        ]
        result = self.scraper._apply_local_filters(
            ads,
            {"bedrooms_min": 2, "area_min": 60, "neighborhoods": ["Centro"]},
        )
        assert len(result) == 1
        assert result[0]["olx_id"] == "1"
