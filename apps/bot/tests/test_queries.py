from shared_models.tables import User
from sqlmodel import Session

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
    )
    session.commit()
    assert alert_id > 0

    found = queries.find_equivalent_alert(
        session,
        chat_id=123456,
        alert_name="Aluguel Jatiúca",
        min_price=800,
        max_price=1500,
        neighbourhoods=["Ponta Verde", "Jatiúca"],
    )
    assert found is not None
    assert found.id == alert_id

    missing = queries.find_equivalent_alert(
        session,
        chat_id=123456,
        alert_name="Aluguel Jatiúca",
        min_price=800,
        max_price=2000,
        neighbourhoods=["Jatiúca", "Ponta Verde"],
    )
    assert missing is None


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
    )
    session.commit()

    found = queries.find_equivalent_alert(
        session,
        chat_id=chat_id,
        alert_name="Aluguel grande chat_id",
        min_price=0,
        max_price=1500,
        neighbourhoods=["Jatiúca"],
    )
    assert found is not None
    assert found.id == alert_id
    assert found.chat_id == chat_id
