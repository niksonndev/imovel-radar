"""Tests for immediate seed scan in wiz_confirm_cb."""
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from database.models import Base, User, Alert
from database.crud import seen_olx_ids
from bot.conversations import wiz_confirm_cb

pytestmark = pytest.mark.asyncio

FAKE_LISTINGS = [
    {"olx_id": "111111111", "title": "Apt 1", "price": 300000,
     "url": "https://olx.com.br/d/111111111"},
    {"olx_id": "222222222", "title": "Apt 2", "price": 450000,
     "url": "https://olx.com.br/d/222222222"},
]


@pytest_asyncio.fixture
async def wizard_env():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    scraper = AsyncMock()
    scraper.search_listings.return_value = FAKE_LISTINGS

    app = MagicMock()
    app.bot_data = {
        "session_factory": factory,
        "scraper": scraper,
        "alert_min": 3,
    }

    query = AsyncMock()
    query.data = "wiz_confirm_yes"
    query.message = AsyncMock()

    update = MagicMock()
    update.callback_query = query
    update.effective_user.id = 99999
    update.effective_user.username = "testuser"

    context = MagicMock()
    context.application = app
    context.application.bot_data = app.bot_data
    context.user_data = {
        "wizard_alert": {
            "name": "Ape noco",
            "transaction": "sale",
            "price_min": None,
            "price_max": 300000,
            "neighborhoods_selected": set(),
        }
    }

    yield factory, update, context, scraper, query


async def test_wizard_sends_seed_message_immediately(wizard_env):
    """Ao confirmar alerta, envia mensagem de resumo imediatamente."""
    factory, update, context, scraper, query = wizard_env

    await wiz_confirm_cb(update, context)

    query.message.reply_text.assert_called()
    last_call = query.message.reply_text.call_args_list[-1]
    text = last_call[1].get("text") or last_call[0][0]
    assert "Alerta Ape noco ativado" in text
    assert "2 imóveis" in text
    assert "Ver resultados no OLX" in text
    assert "verifico essa busca" in text


async def test_wizard_populates_seen_listings(wizard_env):
    """Ao confirmar, marca todos os listings como vistos."""
    factory, update, context, scraper, query = wizard_env

    await wiz_confirm_cb(update, context)

    async with factory() as session:
        from database.crud import list_alerts, get_or_create_user
        user = await get_or_create_user(session, 99999, "testuser")
        alerts = await list_alerts(session, user.id)
        assert len(alerts) == 1
        seen = await seen_olx_ids(session, alerts[0].id)
    assert seen == {"111111111", "222222222"}


async def test_wizard_sets_last_checked(wizard_env):
    """Após seed imediato, last_checked não deve ser None."""
    factory, update, context, scraper, query = wizard_env

    await wiz_confirm_cb(update, context)

    async with factory() as session:
        from database.crud import list_alerts, get_or_create_user
        user = await get_or_create_user(session, 99999, "testuser")
        alerts = await list_alerts(session, user.id)
        assert alerts[0].last_checked is not None


async def test_wizard_fallback_on_scrape_failure(wizard_env):
    """Se o scraping falhar, envia mensagem de fallback e NÃO seta last_checked."""
    factory, update, context, scraper, query = wizard_env
    scraper.search_listings.side_effect = Exception("OLX bloqueou")

    await wiz_confirm_cb(update, context)

    last_call = query.message.reply_text.call_args_list[-1]
    text = last_call[1].get("text") or last_call[0][0]
    assert "criado" in text
    assert "Primeira verificação" in text
    assert "ativado" not in text

    async with factory() as session:
        from database.crud import list_alerts, get_or_create_user
        user = await get_or_create_user(session, 99999, "testuser")
        alerts = await list_alerts(session, user.id)
        assert alerts[0].last_checked is None
