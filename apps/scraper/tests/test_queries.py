import json
from pathlib import Path

from shared_models.tables import Listing
from sqlmodel import Session

from collector.parser import RawAd
from database.queries import get_neighbourhoods, upsert_listing

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