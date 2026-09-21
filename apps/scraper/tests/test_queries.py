import json
from datetime import UTC, datetime, timedelta
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
    assert stored.listing_kind == "aluguel"
    assert stored.updated_at is not None


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
                listing_kind="aluguel",
            )
        )
    session.commit()

    result = get_neighbourhoods(session, "Maceió")

    assert set(result) == set(names)
    assert all(len(name) > 1 for name in result)


def test_get_neighbourhoods_filters_by_listing_kind(session: Session) -> None:
    session.add(
        _listing(1, listing_kind="aluguel", neighbourhood="Prado")
    )
    session.add(
        _listing(2, listing_kind="venda", neighbourhood="Jatiúca")
    )
    session.commit()

    rent = get_neighbourhoods(session, "Maceió", listing_kind="aluguel")
    sale = get_neighbourhoods(session, "Maceió", listing_kind="venda")

    assert rent == ["Prado"]
    assert sale == ["Jatiúca"]


def _listing(
    listing_id: int,
    municipality: str = "Maceió",
    *,
    active: bool = True,
    listing_kind: str = "aluguel",
    neighbourhood: str = "Centro",
    updated_at: datetime | None = None,
) -> Listing:
    return Listing(
        listing_id=listing_id,
        url=f"https://exemplo.com/{listing_id}",
        title=f"Imóvel {listing_id}",
        municipality=municipality,
        neighbourhood=neighbourhood,
        category="Apartamento",
        images=[],
        properties={},
        active=active,
        listing_kind=listing_kind,  # type: ignore[arg-type]
        updated_at=updated_at,
    )


def test_deactivate_missing_listings_inactivates_stale_by_kind(session: Session) -> None:
    run_started = datetime.now(UTC)
    stale = run_started - timedelta(hours=1)
    session.add(_listing(1, listing_kind="aluguel", updated_at=run_started))
    session.add(_listing(2, listing_kind="aluguel", updated_at=stale))
    session.add(_listing(3, listing_kind="venda", updated_at=stale))
    session.commit()

    n = deactivate_missing_listings(
        session,
        municipality="Maceió",
        listing_kind="aluguel",
        run_started_at=run_started,
    )
    session.commit()
    session.expire_all()

    assert n == 1
    assert session.get(Listing, 1).active is True  # type: ignore[union-attr]
    assert session.get(Listing, 2).active is False  # type: ignore[union-attr]
    assert session.get(Listing, 3).active is True  # type: ignore[union-attr]


def test_deactivate_missing_listings_does_not_touch_other_kind(session: Session) -> None:
    run_started = datetime.now(UTC)
    stale = run_started - timedelta(minutes=5)
    session.add(_listing(1, listing_kind="venda", updated_at=stale))
    session.add(_listing(2, listing_kind="aluguel", updated_at=stale))
    session.commit()

    n = deactivate_missing_listings(
        session,
        municipality="Maceió",
        listing_kind="venda",
        run_started_at=run_started,
    )
    session.commit()
    session.expire_all()

    assert n == 1
    assert session.get(Listing, 1).active is False  # type: ignore[union-attr]
    assert session.get(Listing, 2).active is True  # type: ignore[union-attr]


def test_deactivate_missing_listings_scopes_by_municipality(session: Session) -> None:
    run_started = datetime.now(UTC)
    stale = run_started - timedelta(minutes=1)
    session.add(_listing(1, "Maceió", updated_at=stale))
    session.add(_listing(2, "Recife", updated_at=stale))
    session.commit()

    n = deactivate_missing_listings(
        session,
        municipality="Maceió",
        listing_kind="aluguel",
        run_started_at=run_started,
    )
    session.commit()
    session.expire_all()

    assert n == 1
    assert session.get(Listing, 1).active is False  # type: ignore[union-attr]
    assert session.get(Listing, 2).active is True  # type: ignore[union-attr]


def test_deactivate_null_updated_at_is_stale(session: Session) -> None:
    run_started = datetime.now(UTC)
    session.add(_listing(1, updated_at=None))
    session.commit()

    n = deactivate_missing_listings(
        session,
        municipality="Maceió",
        listing_kind="aluguel",
        run_started_at=run_started,
    )
    session.commit()
    session.expire_all()

    assert n == 1
    assert session.get(Listing, 1).active is False  # type: ignore[union-attr]
