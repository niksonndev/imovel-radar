"""
CRUD = Create, Read, Update, Delete — funções que falam com o banco.

Todas são "async" porque usamos SQLAlchemy async (await = espera o disco terminar).
session = uma "transação" curta: abre, faz coisas, commit ou rollback.
"""
from datetime import datetime
from typing import Any, Sequence

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from database.models import User, Alert, SeenListing, WatchedListing


def create_engine_and_session(database_url: str):
    # engine = conexão com o arquivo SQLite (ou outro banco na URL)
    engine = create_async_engine(database_url, echo=False)
    # session_factory = função que cria novas sessões quando precisamos
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    return engine, session_factory


async def init_db(engine) -> None:
    """Cria todas as tabelas definidas em models.py (CREATE TABLE se não existir)."""
    from database.models import Base

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_or_create_user(
    session: AsyncSession, telegram_id: int, username: str | None
) -> User:
    """Garante que existe um User para esse chat_id do Telegram."""
    r = await session.execute(select(User).where(User.telegram_id == telegram_id))
    u = r.scalar_one_or_none()
    if u:
        if username and u.username != username:
            u.username = username
            await session.commit()
        return u
    u = User(telegram_id=telegram_id, username=username)
    session.add(u)
    await session.commit()
    await session.refresh(u)  # preenche u.id gerado pelo banco
    return u


async def create_alert(
    session: AsyncSession, user_id: int, name: str, filters: dict[str, Any]
) -> Alert:
    a = Alert(user_id=user_id, name=name, filters=filters, is_active=True)
    session.add(a)
    await session.commit()
    await session.refresh(a)
    return a


async def list_alerts(session: AsyncSession, user_id: int) -> Sequence[Alert]:
    r = await session.execute(
        select(Alert).where(Alert.user_id == user_id).order_by(Alert.created_at.desc())
    )
    return r.scalars().all()


async def get_alert(session: AsyncSession, alert_id: int, user_id: int) -> Alert | None:
    r = await session.execute(
        select(Alert).where(Alert.id == alert_id, Alert.user_id == user_id)
    )
    return r.scalar_one_or_none()


async def toggle_alert_active(session: AsyncSession, alert_id: int, user_id: int) -> bool | None:
    a = await get_alert(session, alert_id, user_id)
    if not a:
        return None
    a.is_active = not a.is_active
    await session.commit()
    return a.is_active


async def delete_alert(session: AsyncSession, alert_id: int, user_id: int) -> bool:
    a = await get_alert(session, alert_id, user_id)
    if not a:
        return False
    await session.delete(a)
    await session.commit()
    return True


async def mark_seen(session: AsyncSession, alert_id: int, olx_id: str) -> bool:
    """
    Registra que já vimos esse anúncio neste alerta.
    Retorna True só na PRIMEIRA vez (anúncio novo → vale notificar no Telegram).
    """
    r = await session.execute(
        select(SeenListing).where(
            SeenListing.alert_id == alert_id, SeenListing.olx_id == olx_id
        )
    )
    row = r.scalar_one_or_none()
    now = datetime.utcnow()
    if row:
        row.last_seen = now
        await session.commit()
        return False
    session.add(SeenListing(alert_id=alert_id, olx_id=olx_id, first_seen=now, last_seen=now))
    await session.commit()
    return True


async def seen_olx_ids(session: AsyncSession, alert_id: int) -> set[str]:
    r = await session.execute(select(SeenListing.olx_id).where(SeenListing.alert_id == alert_id))
    return set(r.scalars().all())


async def update_alert_last_checked(session: AsyncSession, alert_id: int) -> None:
    await session.execute(
        update(Alert).where(Alert.id == alert_id).values(last_checked=datetime.utcnow())
    )
    await session.commit()


async def active_alerts(session: AsyncSession) -> Sequence[Alert]:
    """Todos os alertas ligados (o job de scraping roda em cima disso)."""
    r = await session.execute(select(Alert).where(Alert.is_active == True))  # noqa: E712
    return r.scalars().all()


# ---------- Watchlist ----------


async def add_watched(
    session: AsyncSession,
    user_id: int,
    olx_id: str,
    url: str,
    title: str | None,
    initial_price: float | None,
) -> WatchedListing:
    w = WatchedListing(
        user_id=user_id,
        olx_id=olx_id,
        url=url,
        title=title,
        initial_price=initial_price,
        current_price=initial_price,
        price_history=[{"price": initial_price, "at": datetime.utcnow().isoformat()}]
        if initial_price is not None
        else [],
        is_active=True,
        removed_notified=False,
    )
    session.add(w)
    await session.commit()
    await session.refresh(w)
    return w


async def list_watched(session: AsyncSession, user_id: int) -> Sequence[WatchedListing]:
    r = await session.execute(
        select(WatchedListing)
        .where(WatchedListing.user_id == user_id, WatchedListing.is_active == True)  # noqa
        .order_by(WatchedListing.id.desc())
    )
    return r.scalars().all()


async def all_active_watched(session: AsyncSession) -> Sequence[WatchedListing]:
    """Itens que o job de watchlist ainda deve checar (não avisamos remoção ainda)."""
    r = await session.execute(
        select(WatchedListing).where(
            WatchedListing.is_active == True, WatchedListing.removed_notified == False  # noqa
        )
    )
    return r.scalars().all()


async def get_watched_by_id(
    session: AsyncSession, wid: int, user_id: int
) -> WatchedListing | None:
    r = await session.execute(
        select(WatchedListing).where(WatchedListing.id == wid, WatchedListing.user_id == user_id)
    )
    return r.scalar_one_or_none()


async def remove_watched(session: AsyncSession, wid: int, user_id: int) -> bool:
    w = await get_watched_by_id(session, wid, user_id)
    if not w:
        return False
    w.is_active = False  # soft delete: não apagamos a linha, só desligamos
    await session.commit()
    return True


async def update_watched_price(
    session: AsyncSession,
    w: WatchedListing,
    new_price: float | None,
    history_entry: dict,
) -> None:
    w.current_price = new_price
    w.last_checked = datetime.utcnow()
    hist = list(w.price_history or [])
    hist.append(history_entry)
    w.price_history = hist[-50:]  # guarda só os últimos 50 pontos
    await session.commit()


async def mark_watched_removed(session: AsyncSession, w: WatchedListing) -> None:
    w.removed_notified = True
    w.is_active = False
    w.last_checked = datetime.utcnow()
    await session.commit()
