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

    assert session.exec(select(AlertMatch).where(AlertMatch.alert_id == alert_id)).first() is not None
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
    assert [m.listing_id for m in queries.get_unnotified_listings_for_alert(session, tab_alert)] == [
        20
    ]


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
