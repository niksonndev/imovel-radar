import json
from pathlib import Path

from shared_models.tables import Listing
from sqlmodel import Session

from collector.parser import RawAd
from database.queries import deactivate_missing_listings, get_neighbourhoods, upsert_listing

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


def test_get_neighbourhoods_returns_full_names(session: Session) -> None:
    """Garante que `get_neighbourhoods` devolve os bairros por extenso.

    Regressão do bug em que `row[0]` sobre valores escalares do SQLModel
    retornava apenas a primeira letra de cada bairro.
    """
    names = ["Ponta Verde", "Jatiúca", "Centro", "Prado"]
    for i, name in enumerate(names, start=1):
        session.add(
            Listing(
                listing_id=i,
                url=f"https://exemplo.com/{i}",
                title=f"Imóvel {i}",
                municipality="Maceió",
                neighbourhood=name,
                category="Apartamento",
                images=[],
                properties={},
            )
        )
    session.commit()

    result = get_neighbourhoods(session, "Maceió")

    # Retorna os nomes completos (e não apenas a inicial).
    assert set(result) == set(names)
    assert all(len(name) > 1 for name in result)


def _listing(listing_id: int, municipality: str = "Maceió", *, active: bool = True) -> Listing:
    return Listing(
        listing_id=listing_id,
        url=f"https://exemplo.com/{listing_id}",
        title=f"Imóvel {listing_id}",
        municipality=municipality,
        neighbourhood="Centro",
        category="Apartamento",
        images=[],
        properties={},
        active=active,
    )


def test_deactivate_missing_listings_inactivates_unseen(session: Session) -> None:
    session.add(_listing(1))
    session.add(_listing(2))
    session.commit()

    n = deactivate_missing_listings(session, {1}, "Maceió")
    session.commit()
    session.expire_all()

    assert n == 1
    seen = session.get(Listing, 1)
    unseen = session.get(Listing, 2)
    assert seen is not None and seen.active is True
    assert unseen is not None and unseen.active is False


def test_deactivate_missing_listings_empty_seen_ids_is_noop(session: Session) -> None:
    session.add(_listing(1))
    session.commit()

    n = deactivate_missing_listings(session, set(), "Maceió")
    session.expire_all()

    assert n == 0
    stored = session.get(Listing, 1)
    assert stored is not None and stored.active is True


def test_deactivate_missing_listings_scopes_by_municipality(session: Session) -> None:
    session.add(_listing(1, "Maceió"))
    session.add(_listing(2, "Recife"))
    session.commit()

    n = deactivate_missing_listings(session, {999}, "Maceió")
    session.commit()
    session.expire_all()

    assert n == 1
    maceio = session.get(Listing, 1)
    recife = session.get(Listing, 2)
    assert maceio is not None and maceio.active is False
    assert recife is not None and recife.active is True
