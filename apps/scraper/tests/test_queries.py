import json
from pathlib import Path

from sqlmodel import Session, SQLModel, create_engine

from collector.parser import RawAd
from database.models import Listing
from database.queries import upsert_listing

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _load_fixture(name: str) -> RawAd:
    return json.loads((FIXTURES_DIR / name).read_text(encoding="utf-8"))


def test_upsert_listing_inserts_from_raw_ad() -> None:
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)

    listing: RawAd = _load_fixture("parsed_olx_ad.json")

    with Session(engine) as session:
        upsert_listing(session, listing)
        session.commit()

        stored = session.get(Listing, listing["listing_id"])
        assert stored is not None
        assert stored.listing_id == listing["listing_id"]


def test_upsert_listing_updates_existing_by_listing_id() -> None:
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)

    listing = _load_fixture("parsed_olx_ad.json")

    with Session(engine) as session:
        upsert_listing(session, listing)
        session.commit()

    updated: RawAd = {**listing, "price_value": 2500, "old_price": listing["price_value"]}

    with Session(engine) as session:
        upsert_listing(session, updated)
        session.commit()

        stored = session.get(Listing, listing["listing_id"])
        assert stored is not None
        assert stored.price_value == 2500
        assert stored.old_price == listing["price_value"]
