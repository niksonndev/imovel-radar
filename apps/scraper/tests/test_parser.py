from __future__ import annotations

import json
from pathlib import Path

from collector import olx_scraper
from collector.parser import normalize_olx_listing

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _load_fixture(name: str) -> dict:
    return json.loads((FIXTURES_DIR / name).read_text(encoding="utf-8"))


def test_normalize_olx_listing_matches_fixture() -> None:
    raw_listing = _load_fixture("raw_olx_ad.json")
    expected_listing = _load_fixture("parsed_olx_ad.json")

    listing = normalize_olx_listing(raw_listing)

    assert listing == expected_listing


def test_extract_listings_from_search_page_uses_real_fixture(monkeypatch) -> None:
    raw_listing = _load_fixture("raw_olx_ad.json")
    expected_listing = _load_fixture("parsed_olx_ad.json")

    monkeypatch.setattr(
        olx_scraper, "_extract_ads_container_from_rsc", lambda html: {"ads": [raw_listing]}
    )
    monkeypatch.setattr(olx_scraper, "_extract_ads_payload", lambda container: [raw_listing])

    listings = olx_scraper.extract_listings_from_search_page("<html></html>")

    assert len(listings) == 1
    assert listings[0] == expected_listing
