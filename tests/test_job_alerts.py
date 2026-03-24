"""Tests for scheduler/jobs.py — seed_only first-cycle behavior."""
import logging
import pytest
import pytest_asyncio
from collections import defaultdict
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from database.models import Base, User, Alert
from database.crud import init_db, mark_seen, create_alert, get_or_create_user
from scheduler.jobs import job_alerts

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def db_factory():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with factory() as session:
        user = User(telegram_id=123456, username="test")
        session.add(user)
        await session.commit()
        await session.refresh(user)
        alert = Alert(
            user_id=user.id,
            name="Apt Jatiúca",
            filters={"transaction": "rent", "property_type": "apartment"},
            is_active=True,
            last_checked=None,
        )
        session.add(alert)
        await session.commit()
        await session.refresh(alert)

    yield factory, user, alert


def _fake_app(factory, bot_mock, scraper_mock):
    app = MagicMock()
    app.bot = bot_mock
    app.bot_data = {
        "session_factory": factory,
        "scraper": scraper_mock,
        "scrape_days": 1,
        "watch_days": 1,
    }
    app.user_data = defaultdict(dict)
    return app


FAKE_LISTINGS = [
    {"olx_id": "111111111", "title": "Apt 1", "price": 300000, "url": "https://olx.com.br/d/111111111",
     "thumbnail": None, "neighborhood": "Jatiúca", "bedrooms": 2, "area_m2": 60},
    {"olx_id": "222222222", "title": "Apt 2", "price": 450000, "url": "https://olx.com.br/d/222222222",
     "thumbnail": None, "neighborhood": "Ponta Verde", "bedrooms": 3, "area_m2": 80},
]


async def test_seed_only_sends_summary_message(db_factory):
    """Primeiro ciclo (last_checked=None) deve enviar mensagem de resumo."""
    factory, user, alert = db_factory
    bot = AsyncMock()
    scraper = AsyncMock()
    scraper.search_all_rent_maceio.return_value = FAKE_LISTINGS

    app = _fake_app(factory, bot, scraper)
    await job_alerts(app)

    bot.send_message.assert_called_once()
    call_kwargs = bot.send_message.call_args[1]
    assert call_kwargs["chat_id"] == 123456
    assert "Apt Jatiúca" in call_kwargs["text"]
    assert "ativado" in call_kwargs["text"]
    assert "2" in call_kwargs["text"]


async def test_seed_only_populates_seen_listings(db_factory):
    """Primeiro ciclo deve gravar seen_listings no banco."""
    factory, user, alert = db_factory
    bot = AsyncMock()
    scraper = AsyncMock()
    scraper.search_all_rent_maceio.return_value = FAKE_LISTINGS

    app = _fake_app(factory, bot, scraper)
    await job_alerts(app)

    from database.crud import seen_olx_ids
    async with factory() as session:
        seen = await seen_olx_ids(session, alert.id)
    assert seen == {"111111111", "222222222"}


async def test_seed_only_does_not_send_individual_notifications(db_factory):
    """Primeiro ciclo NÃO deve enviar notificações individuais por anúncio."""
    factory, user, alert = db_factory
    bot = AsyncMock()
    scraper = AsyncMock()
    scraper.search_all_rent_maceio.return_value = FAKE_LISTINGS

    app = _fake_app(factory, bot, scraper)
    await job_alerts(app)

    assert bot.send_message.call_count == 1
    assert "Novo imóvel encontrado" not in bot.send_message.call_args[1]["text"]


async def test_second_cycle_sends_carousel_for_new(db_factory):
    """Segundo ciclo deve enviar resumo + carrossel com anúncios novos."""
    factory, user, alert = db_factory
    bot = AsyncMock()
    scraper = AsyncMock()

    scraper.search_all_rent_maceio.return_value = FAKE_LISTINGS
    app = _fake_app(factory, bot, scraper)
    await job_alerts(app)

    bot.reset_mock()
    new_listings = FAKE_LISTINGS + [
        {"olx_id": "333333333", "title": "Apt 3", "price": 500000, "url": "https://olx.com.br/d/333333333",
         "thumbnail": None, "neighborhood": "Pajuçara", "bedrooms": 3, "area_m2": 90},
    ]
    scraper.search_all_rent_maceio.return_value = new_listings
    await job_alerts(app)

    calls = bot.send_message.call_args_list
    assert len(calls) == 2
    summary_text = calls[0][1]["text"]
    assert "Alerta" in summary_text
    assert "1" in summary_text

    carousel_text = calls[1][1].get("text", "")
    assert "Apt 3" in carousel_text
    assert "1 de 1" in carousel_text
    assert "Página 1 de 1" in carousel_text


async def test_seed_only_no_listings(db_factory):
    """Primeiro ciclo sem listings deve enviar resumo com count=0."""
    factory, user, alert = db_factory
    bot = AsyncMock()
    scraper = AsyncMock()
    scraper.search_all_rent_maceio.return_value = []

    app = _fake_app(factory, bot, scraper)
    await job_alerts(app)

    bot.send_message.assert_called_once()
    assert "*0*" in bot.send_message.call_args[1]["text"]


async def test_seed_message_contains_olx_link(db_factory):
    """Mensagem de resumo deve conter link para resultados no OLX."""
    factory, user, alert = db_factory
    bot = AsyncMock()
    scraper = AsyncMock()
    scraper.search_all_rent_maceio.return_value = FAKE_LISTINGS

    app = _fake_app(factory, bot, scraper)
    await job_alerts(app)

    text = bot.send_message.call_args[1]["text"]
    assert "Ver no OLX" in text
    assert "olx.com.br" in text


async def test_seed_logs_before_and_after(db_factory, caplog):
    """Deve logar info antes e depois do envio do seed."""
    factory, user, alert = db_factory
    bot = AsyncMock()
    scraper = AsyncMock()
    scraper.search_all_rent_maceio.return_value = FAKE_LISTINGS

    app = _fake_app(factory, bot, scraper)
    with caplog.at_level(logging.INFO, logger="scheduler.jobs"):
        await job_alerts(app)

    seed_logs = [r for r in caplog.records if "seed_only" in r.message]
    assert len(seed_logs) >= 2
    assert any("enviando resumo" in r.message for r in seed_logs)
    assert any("enviada com sucesso" in r.message for r in seed_logs)


async def test_seed_send_failure_logs_exception(db_factory, caplog):
    """Se send_message falhar no seed, deve logar com logger.exception."""
    factory, user, alert = db_factory
    bot = AsyncMock()
    bot.send_message.side_effect = Exception("Telegram API error")
    scraper = AsyncMock()
    scraper.search_all_rent_maceio.return_value = FAKE_LISTINGS

    app = _fake_app(factory, bot, scraper)
    with caplog.at_level(logging.ERROR, logger="scheduler.jobs"):
        await job_alerts(app)

    assert any("falha ao enviar resumo" in r.message for r in caplog.records)


async def test_seed_sets_last_checked(db_factory):
    """Após o seed, last_checked deve ser atualizado (não None)."""
    factory, user, alert = db_factory
    bot = AsyncMock()
    scraper = AsyncMock()
    scraper.search_all_rent_maceio.return_value = FAKE_LISTINGS

    app = _fake_app(factory, bot, scraper)
    await job_alerts(app)

    async with factory() as session:
        refreshed = await session.get(Alert, alert.id)
        assert refreshed.last_checked is not None


async def test_wizard_filters_work_with_seed(db_factory):
    """Filtros sem property_type (como o wizard cria) devem funcionar no seed."""
    factory, user, _ = db_factory

    async with factory() as session:
        alert = await create_alert(session, user.id, "Ape noco", {
            "transaction": "rent",
            "price_min": None,
            "price_max": 300000,
            "neighborhoods": [],
        })

    bot = AsyncMock()
    scraper = AsyncMock()
    scraper.search_all_rent_maceio.return_value = FAKE_LISTINGS

    app = _fake_app(factory, bot, scraper)
    await job_alerts(app)

    calls = bot.send_message.call_args_list
    seed_calls = [c for c in calls if "ativado" in c[1].get("text", "")]
    assert len(seed_calls) >= 1
    text = seed_calls[-1][1]["text"]
    assert "Ape noco" in text
    assert "verifico essa busca" in text
