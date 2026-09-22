from shared_models.tables import AlertMatch, Listing, User
from sqlmodel import Session, select

from database import queries


def test_create_alert_and_find_equivalent(session: Session) -> None:
    session.add(User(chat_id=123456))
    session.commit()

    alert_id = queries.create_alert(
        session,
        chat_id=123456,
        alert_name="Aluguel Jatiúca",
        min_price=800,
        max_price=1500,
        neighbourhoods=["Jatiúca", "Ponta Verde"],
        listing_kind="aluguel",
    )
    session.commit()
    assert alert_id > 0

    # Same filters, different name → still equivalent.
    found = queries.find_equivalent_alert(
        session,
        chat_id=123456,
        min_price=800,
        max_price=1500,
        neighbourhoods=["Ponta Verde", "Jatiúca"],
        listing_kind="aluguel",
    )
    assert found is not None
    assert found.id == alert_id

    missing = queries.find_equivalent_alert(
        session,
        chat_id=123456,
        min_price=800,
        max_price=2000,
        neighbourhoods=["Jatiúca", "Ponta Verde"],
        listing_kind="aluguel",
    )
    assert missing is None


def test_equivalent_alert_differs_by_listing_kind(session: Session) -> None:
    session.add(User(chat_id=99))
    session.commit()

    rent_id = queries.create_alert(
        session,
        chat_id=99,
        alert_name="Centro",
        min_price=1000,
        max_price=2000,
        neighbourhoods=["Centro"],
        listing_kind="aluguel",
    )
    sale_id = queries.create_alert(
        session,
        chat_id=99,
        alert_name="Centro",
        min_price=1000,
        max_price=2000,
        neighbourhoods=["Centro"],
        listing_kind="venda",
    )
    session.commit()

    assert rent_id != sale_id
    rent = queries.find_equivalent_alert(
        session,
        chat_id=99,
        min_price=1000,
        max_price=2000,
        neighbourhoods=["Centro"],
        listing_kind="aluguel",
    )
    sale = queries.find_equivalent_alert(
        session,
        chat_id=99,
        min_price=1000,
        max_price=2000,
        neighbourhoods=["Centro"],
        listing_kind="venda",
    )
    assert rent is not None and rent.id == rent_id
    assert sale is not None and sale.id == sale_id


def test_equivalent_alert_differs_by_min_rooms(session: Session) -> None:
    session.add(User(chat_id=88))
    session.commit()

    any_id = queries.create_alert(
        session,
        chat_id=88,
        alert_name="Qualquer",
        min_price=800,
        max_price=1500,
        neighbourhoods=["Jatiúca"],
        listing_kind="aluguel",
        min_rooms=None,
    )
    two_id = queries.create_alert(
        session,
        chat_id=88,
        alert_name="2+",
        min_price=800,
        max_price=1500,
        neighbourhoods=["Jatiúca"],
        listing_kind="aluguel",
        min_rooms=2,
    )
    session.commit()
    assert any_id != two_id

    found_any = queries.find_equivalent_alert(
        session,
        chat_id=88,
        min_price=800,
        max_price=1500,
        neighbourhoods=["Jatiúca"],
        listing_kind="aluguel",
        min_rooms=None,
    )
    found_two = queries.find_equivalent_alert(
        session,
        chat_id=88,
        min_price=800,
        max_price=1500,
        neighbourhoods=["Jatiúca"],
        listing_kind="aluguel",
        min_rooms=2,
    )
    assert found_any is not None and found_any.id == any_id
    assert found_two is not None and found_two.id == two_id
    assert (
        queries.find_equivalent_alert(
            session,
            chat_id=88,
            min_price=800,
            max_price=1500,
            neighbourhoods=["Jatiúca"],
            listing_kind="aluguel",
            min_rooms=3,
        )
        is None
    )


def test_unnotified_listings_filter_by_min_rooms(session: Session) -> None:
    session.add(User(chat_id=77))
    session.add(
        Listing(
            listing_id=101,
            url="https://ex/101",
            title="3 quartos",
            price_value=1200,
            municipality="Maceió",
            neighbourhood="Centro",
            category="Apartamentos",
            images=["https://img/101.webp"],
            properties={"rooms": 3},
            listing_kind="aluguel",
            active=True,
        )
    )
    session.add(
        Listing(
            listing_id=102,
            url="https://ex/102",
            title="1 quarto",
            price_value=1200,
            municipality="Maceió",
            neighbourhood="Centro",
            category="Apartamentos",
            images=["https://img/102.webp"],
            properties={"rooms": 1},
            listing_kind="aluguel",
            active=True,
        )
    )
    session.add(
        Listing(
            listing_id=103,
            url="https://ex/103",
            title="Sem quartos",
            price_value=1200,
            municipality="Maceió",
            neighbourhood="Centro",
            category="Apartamentos",
            images=["https://img/103.webp"],
            properties={},
            listing_kind="aluguel",
            active=True,
        )
    )
    session.commit()

    alert_id = queries.create_alert(
        session,
        chat_id=77,
        alert_name="2+ Centro",
        min_price=500,
        max_price=2000,
        neighbourhoods=["Centro"],
        listing_kind="aluguel",
        min_rooms=2,
    )
    session.commit()
    alert = queries.get_alert_for_user(session, 77, alert_id)
    assert alert is not None

    matches = queries.get_unnotified_listings_for_alert(session, alert)
    assert sorted(m.listing_id for m in matches) == [101, 103]


def test_unnotified_listings_no_min_rooms_includes_all(session: Session) -> None:
    session.add(User(chat_id=76))
    session.add(
        Listing(
            listing_id=201,
            url="https://ex/201",
            title="1 quarto",
            price_value=1000,
            municipality="Maceió",
            neighbourhood="Centro",
            category="Apartamentos",
            images=["https://img/201.webp"],
            properties={"rooms": 1},
            listing_kind="aluguel",
            active=True,
        )
    )
    session.add(
        Listing(
            listing_id=202,
            url="https://ex/202",
            title="Sem quartos",
            price_value=1000,
            municipality="Maceió",
            neighbourhood="Centro",
            category="Apartamentos",
            images=["https://img/202.webp"],
            properties={},
            listing_kind="aluguel",
            active=True,
        )
    )
    session.commit()

    alert_id = queries.create_alert(
        session,
        chat_id=76,
        alert_name="Qualquer",
        min_price=500,
        max_price=2000,
        neighbourhoods=["Centro"],
        listing_kind="aluguel",
        min_rooms=None,
    )
    session.commit()
    alert = queries.get_alert_for_user(session, 76, alert_id)
    assert alert is not None

    matches = queries.get_unnotified_listings_for_alert(session, alert)
    assert sorted(m.listing_id for m in matches) == [201, 202]


def test_unnotified_listings_filter_by_listing_kind(session: Session) -> None:
    session.add(User(chat_id=7))
    session.add(
        Listing(
            listing_id=1,
            url="https://ex/1",
            title="Aluguel",
            price_value=1000,
            municipality="Maceió",
            neighbourhood="Centro",
            category="Casas",
            images=["https://img/1.webp"],
            properties={},
            listing_kind="aluguel",
            active=True,
        )
    )
    session.add(
        Listing(
            listing_id=2,
            url="https://ex/2",
            title="Venda",
            price_value=1000,
            municipality="Maceió",
            neighbourhood="Centro",
            category="Casas",
            images=["https://img/2.webp"],
            properties={},
            listing_kind="venda",
            active=True,
        )
    )
    session.commit()

    alert_id = queries.create_alert(
        session,
        chat_id=7,
        alert_name="Aluguel Centro",
        min_price=500,
        max_price=2000,
        neighbourhoods=["Centro"],
        listing_kind="aluguel",
    )
    session.commit()
    alert = queries.get_alert_for_user(session, 7, alert_id)
    assert alert is not None

    matches = queries.get_unnotified_listings_for_alert(session, alert)
    assert [m.listing_id for m in matches] == [1]


def test_mark_listings_excludes_from_unnotified(session: Session) -> None:
    session.add(User(chat_id=11))
    session.add(
        Listing(
            listing_id=10,
            url="https://ex/10",
            title="Casa",
            price_value=200_000,
            municipality="Maceió",
            neighbourhood="Antares",
            category="Casas",
            images=["https://img/10.webp"],
            properties={},
            listing_kind="venda",
            active=True,
        )
    )
    session.commit()

    alert_id = queries.create_alert(
        session,
        chat_id=11,
        alert_name="Compra Antares",
        min_price=150_000,
        max_price=300_000,
        neighbourhoods=["Antares"],
        listing_kind="venda",
    )
    session.commit()
    alert = queries.get_alert_for_user(session, 11, alert_id)
    assert alert is not None
    assert [m.listing_id for m in queries.get_unnotified_listings_for_alert(session, alert)] == [10]

    queries.mark_listings_notified(session, [(alert_id, 10)])
    session.commit()
    assert queries.get_unnotified_listings_for_alert(session, alert) == []

    # Idempotent re-mark must not raise.
    queries.mark_listings_notified(session, [(alert_id, 10)])
    session.commit()
    assert queries.get_unnotified_listings_for_alert(session, alert) == []


def test_delete_alert_clears_alert_matches(session: Session) -> None:
    session.add(User(chat_id=22))
    session.add(
        Listing(
            listing_id=20,
            url="https://ex/20",
            title="Apto",
            price_value=180_000,
            municipality="Maceió",
            neighbourhood="Tabuleiro",
            category="Apartamentos",
            images=["https://img/20.webp"],
            properties={},
            listing_kind="venda",
            active=True,
        )
    )
    session.commit()

    alert_id = queries.create_alert(
        session,
        chat_id=22,
        alert_name="Compra",
        min_price=150_000,
        max_price=300_000,
        neighbourhoods=["Antares", "Tabuleiro"],
        listing_kind="venda",
    )
    session.commit()
    queries.mark_listings_notified(session, [(alert_id, 20)])
    session.commit()

    match = session.exec(select(AlertMatch).where(AlertMatch.alert_id == alert_id)).first()
    assert match is not None
    assert queries.delete_alert_for_user(session, 22, alert_id) is True
    session.commit()

    assert session.exec(select(AlertMatch).where(AlertMatch.alert_id == alert_id)).first() is None

    # Recreating with a subset of neighbourhoods is a new alert → listing is unnotified again.
    new_id = queries.create_alert(
        session,
        chat_id=22,
        alert_name="Só Antares",
        min_price=150_000,
        max_price=300_000,
        neighbourhoods=["Antares"],
        listing_kind="venda",
    )
    session.commit()
    # Listing is in Tabuleiro, so Antares-only alert should not match it.
    new_alert = queries.get_alert_for_user(session, 22, new_id)
    assert new_alert is not None
    assert queries.get_unnotified_listings_for_alert(session, new_alert) == []

    tab_id = queries.create_alert(
        session,
        chat_id=22,
        alert_name="Tabuleiro",
        min_price=150_000,
        max_price=300_000,
        neighbourhoods=["Tabuleiro"],
        listing_kind="venda",
    )
    session.commit()
    tab_alert = queries.get_alert_for_user(session, 22, tab_id)
    assert tab_alert is not None
    unnotified = queries.get_unnotified_listings_for_alert(session, tab_alert)
    assert [m.listing_id for m in unnotified] == [20]


def test_ensure_user_is_idempotent(session: Session) -> None:
    queries.ensure_user(session, 42)
    session.commit()
    queries.ensure_user(session, 42)
    session.commit()
    ids = queries.get_users_chat_ids(session)
    assert ids == [42]


def test_large_telegram_chat_id_fits_bigint(session: Session) -> None:
    """Telegram ids can exceed PostgreSQL INTEGER max (2^31-1)."""
    chat_id = 7_217_061_180
    queries.ensure_user(session, chat_id)
    session.commit()

    alert_id = queries.create_alert(
        session,
        chat_id=chat_id,
        alert_name="Aluguel grande chat_id",
        min_price=0,
        max_price=1500,
        neighbourhoods=["Jatiúca"],
        listing_kind="aluguel",
    )
    session.commit()

    found = queries.find_equivalent_alert(
        session,
        chat_id=chat_id,
        min_price=0,
        max_price=1500,
        neighbourhoods=["Jatiúca"],
        listing_kind="aluguel",
    )
    assert found is not None
    assert found.id == alert_id
    assert found.chat_id == chat_id


def _add_listing(
    session: Session,
    listing_id: int,
    *,
    price: int = 1500,
    active: bool = True,
) -> None:
    session.add(
        Listing(
            listing_id=listing_id,
            url=f"https://al.olx.com.br/alagoas/imoveis/x-{listing_id}",
            title=f"Imovel {listing_id}",
            price_value=price,
            municipality="Maceió",
            neighbourhood="Jatiúca",
            category="Apartamentos",
            images=[f"https://img/{listing_id}.webp"],
            properties={},
            listing_kind="aluguel",
            active=active,
        )
    )


def test_create_watch_sets_baselines_and_duplicate(session: Session, monkeypatch) -> None:
    monkeypatch.setattr("config.WATCHLIST_FREE_CAP", 2)
    session.add(User(chat_id=501))
    _add_listing(session, 5010, price=1800)
    session.commit()

    status, watch_id = queries.create_watch(session, chat_id=501, listing_id=5010)
    session.commit()
    assert status == "created"
    assert watch_id is not None

    row = queries.get_watch_for_user(session, 501, watch_id)
    assert row is not None
    assert row.watch.last_known_price == 1800
    assert row.watch.last_known_active is True

    status2, dup_id = queries.create_watch(session, chat_id=501, listing_id=5010)
    assert status2 == "duplicate"
    assert dup_id == watch_id


def test_create_watch_cap_and_missing(session: Session, monkeypatch) -> None:
    monkeypatch.setattr("config.WATCHLIST_FREE_CAP", 2)
    session.add(User(chat_id=502))
    _add_listing(session, 5021, price=1000)
    _add_listing(session, 5022, price=1100)
    _add_listing(session, 5023, price=1200)
    session.commit()

    assert queries.create_watch(session, chat_id=502, listing_id=999999)[0] == "listing_missing"

    s1, _ = queries.create_watch(session, chat_id=502, listing_id=5021)
    s2, _ = queries.create_watch(session, chat_id=502, listing_id=5022)
    session.commit()
    assert s1 == "created"
    assert s2 == "created"
    assert queries.count_watches_for_user(session, 502) == 2

    s3, wid = queries.create_watch(session, chat_id=502, listing_id=5023)
    assert s3 == "cap_reached"
    assert wid is None


def test_changed_watches_and_baseline_update(session: Session, monkeypatch) -> None:
    monkeypatch.setattr("config.WATCHLIST_FREE_CAP", 2)
    session.add(User(chat_id=503))
    _add_listing(session, 5030, price=2000, active=True)
    session.commit()

    status, watch_id = queries.create_watch(session, chat_id=503, listing_id=5030)
    session.commit()
    assert status == "created"
    assert watch_id is not None
    assert queries.get_changed_watches(session) == []

    listing = queries.get_listing(session, 5030)
    assert listing is not None
    listing.price_value = 1700
    session.add(listing)
    session.commit()

    changed = queries.get_changed_watches(session)
    assert len(changed) == 1
    assert changed[0].watch.id == watch_id
    assert changed[0].listing.price_value == 1700

    queries.update_watch_baselines(session, [(watch_id, 1700, True)])
    session.commit()
    assert queries.get_changed_watches(session) == []

    listing = queries.get_listing(session, 5030)
    assert listing is not None
    listing.active = False
    session.add(listing)
    session.commit()

    changed2 = queries.get_changed_watches(session)
    assert len(changed2) == 1
    assert changed2[0].listing.active is False

    queries.update_watch_baselines(session, [(watch_id, 1700, False)])
    session.commit()
    assert queries.get_changed_watches(session) == []


def test_delete_watch_for_user(session: Session, monkeypatch) -> None:
    monkeypatch.setattr("config.WATCHLIST_FREE_CAP", 2)
    session.add(User(chat_id=504))
    _add_listing(session, 5040)
    session.commit()
    _, watch_id = queries.create_watch(session, chat_id=504, listing_id=5040)
    session.commit()
    assert watch_id is not None
    assert queries.delete_watch_for_user(session, 504, watch_id) is True
    session.commit()
    assert queries.get_watches_for_user(session, 504) == []
    assert queries.delete_watch_for_user(session, 504, watch_id) is False
