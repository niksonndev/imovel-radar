"""Tests for database CRUD operations."""
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from database.models import Base
from database.crud import (
    create_alert,
    create_engine_and_session,
    delete_alert,
    get_alert,
    get_or_create_user,
    init_db,
    list_alerts,
    mark_seen,
    seen_olx_ids,
    toggle_alert_active,
    add_watched,
    list_watched,
    remove_watched,
)

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


class TestGetOrCreateUser:
    async def test_create_new(self, db_session):
        u = await get_or_create_user(db_session, telegram_id=111, username="alice")
        assert u.telegram_id == 111
        assert u.username == "alice"
        assert u.id is not None

    async def test_idempotent(self, db_session):
        u1 = await get_or_create_user(db_session, 111, "alice")
        u2 = await get_or_create_user(db_session, 111, "alice")
        assert u1.id == u2.id

    async def test_updates_username(self, db_session):
        await get_or_create_user(db_session, 111, "alice")
        u = await get_or_create_user(db_session, 111, "alice_new")
        assert u.username == "alice_new"


class TestAlertCrud:
    async def test_create_and_list(self, db_session):
        u = await get_or_create_user(db_session, 111, "alice")
        a = await create_alert(db_session, u.id, "Test", {"property_type": "apartment"})
        assert a.name == "Test"
        alerts = await list_alerts(db_session, u.id)
        assert len(alerts) == 1
        assert alerts[0].id == a.id

    async def test_get_alert(self, db_session):
        u = await get_or_create_user(db_session, 111, "alice")
        a = await create_alert(db_session, u.id, "Test", {})
        found = await get_alert(db_session, a.id, u.id)
        assert found is not None
        assert found.id == a.id

    async def test_get_alert_wrong_user(self, db_session):
        u1 = await get_or_create_user(db_session, 111, "alice")
        u2 = await get_or_create_user(db_session, 222, "bob")
        a = await create_alert(db_session, u1.id, "Test", {})
        assert await get_alert(db_session, a.id, u2.id) is None

    async def test_toggle_active(self, db_session):
        u = await get_or_create_user(db_session, 111, "alice")
        a = await create_alert(db_session, u.id, "Test", {})
        assert a.is_active is True
        active = await toggle_alert_active(db_session, a.id, u.id)
        assert active is False
        active = await toggle_alert_active(db_session, a.id, u.id)
        assert active is True

    async def test_toggle_nonexistent(self, db_session):
        assert await toggle_alert_active(db_session, 9999, 9999) is None

    async def test_delete(self, db_session):
        u = await get_or_create_user(db_session, 111, "alice")
        a = await create_alert(db_session, u.id, "Test", {})
        assert await delete_alert(db_session, a.id, u.id) is True
        assert await list_alerts(db_session, u.id) == []

    async def test_delete_nonexistent(self, db_session):
        assert await delete_alert(db_session, 9999, 9999) is False


class TestMarkSeen:
    async def test_first_time_is_new(self, db_session):
        u = await get_or_create_user(db_session, 111, "alice")
        a = await create_alert(db_session, u.id, "Test", {})
        assert await mark_seen(db_session, a.id, "olx_001") is True

    async def test_second_time_is_not_new(self, db_session):
        u = await get_or_create_user(db_session, 111, "alice")
        a = await create_alert(db_session, u.id, "Test", {})
        await mark_seen(db_session, a.id, "olx_001")
        assert await mark_seen(db_session, a.id, "olx_001") is False

    async def test_seen_ids(self, db_session):
        u = await get_or_create_user(db_session, 111, "alice")
        a = await create_alert(db_session, u.id, "Test", {})
        await mark_seen(db_session, a.id, "olx_001")
        await mark_seen(db_session, a.id, "olx_002")
        ids = await seen_olx_ids(db_session, a.id)
        assert ids == {"olx_001", "olx_002"}


class TestWatchlist:
    async def test_add_and_list(self, db_session):
        u = await get_or_create_user(db_session, 111, "alice")
        w = await add_watched(
            db_session, u.id, "olx_001", "https://olx.com.br/d/1", "Apto", 300000.0
        )
        assert w.olx_id == "olx_001"
        items = await list_watched(db_session, u.id)
        assert len(items) == 1

    async def test_remove(self, db_session):
        u = await get_or_create_user(db_session, 111, "alice")
        w = await add_watched(
            db_session, u.id, "olx_001", "https://olx.com.br/d/1", "Apto", 300000.0
        )
        assert await remove_watched(db_session, w.id, u.id) is True
        items = await list_watched(db_session, u.id)
        assert len(items) == 0

    async def test_remove_nonexistent(self, db_session):
        assert await remove_watched(db_session, 9999, 9999) is False
