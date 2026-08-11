import json
from pathlib import Path

from shared_models.api_schemas import CreateAlertRequest
from sqlmodel import Session

from collector.parser import RawAd
from database.models import Alert, Listing, User
from database.queries import create_alert, upsert_listing

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _load_fixture(name: str) -> RawAd:
    return json.loads((FIXTURES_DIR / name).read_text(encoding="utf-8"))


def test_upsert_listing_inserts_from_raw_ad(session: Session) -> None:
    listing: RawAd = _load_fixture("parsed_olx_ad.json")

    upsert_listing(session, listing)
    session.commit()

    stored = session.get(Listing, listing["listing_id"])
    assert stored is not None
    assert stored.listing_id == listing["listing_id"]


def test_upsert_listing_updates_existing_by_listing_id(session: Session) -> None:
    engine = session.get_bind()
    listing = _load_fixture("parsed_olx_ad.json")

    with Session(engine) as s1:
        upsert_listing(s1, listing)
        s1.commit()

    updated: RawAd = {**listing, "price_value": 2500, "old_price": listing["price_value"]}

    with Session(engine) as s2:
        upsert_listing(s2, updated)
        s2.commit()

        stored = s2.get(Listing, listing["listing_id"])
        assert stored is not None
        assert stored.price_value == 2500
        assert stored.old_price == listing["price_value"]


def test_create_alert_persists_fields(session: Session) -> None:
    engine = session.get_bind()

    with Session(engine) as setup:
        user = User(chat_id=123456)
        setup.add(user)
        setup.commit()

    alert_data = CreateAlertRequest(
        chat_id=123456,
        alert_name="Apto 2 quartos Ponta Verde",
        min_price=200_000,
        max_price=400_000,
        neighbourhoods=["Ponta Verde", "Jatiúca"],
    )

    alert_id = create_alert(session, alert_data)
    session.commit()

    with Session(engine) as verify:
        stored = verify.get(Alert, alert_id)
        assert stored is not None
        assert stored.chat_id == alert_data.chat_id
        assert stored.alert_name == alert_data.alert_name
        assert stored.min_price == alert_data.min_price
        assert stored.max_price == alert_data.max_price
        assert stored.neighbourhoods == alert_data.neighbourhoods