"""Tests for immediate seed + carousel after alert confirmation."""
import asyncio

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from database.models import Base, Alert
from database.crud import (
    create_alert,
    get_or_create_user,
    seen_olx_ids,
)
from bot.carousel import (
    immediate_seed,
    _carousel_caption,
    _carousel_keyboard,
    PAGE_SIZE,
    MAX_CAROUSEL,
)
from bot.conversations import wiz_confirm_cb

pytestmark = pytest.mark.asyncio

FAKE_LISTINGS = [
    {
        "olx_id": "111111111",
        "title": "Apt 1",
        "price": 300000,
        "url": "https://olx.com.br/d/111111111",
        "thumbnail": "https://img.olx.com.br/1.jpg",
        "neighborhood": "Jatiúca",
        "bedrooms": 2,
        "area_m2": 60,
    },
    {
        "olx_id": "222222222",
        "title": "Apt 2",
        "price": 450000,
        "url": "https://olx.com.br/d/222222222",
        "thumbnail": None,
        "neighborhood": "Ponta Verde",
        "bedrooms": 3,
        "area_m2": 80,
    },
]


# ─── fixture para testes de immediate_seed ───


@pytest_asyncio.fixture
async def seed_env():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with factory() as session:
        user = await get_or_create_user(session, 99999, "testuser")
        alert = await create_alert(
            session,
            user.id,
            "Ape noco",
            {
                "transaction": "sale",
                "price_min": None,
                "price_max": 300000,
                "neighborhoods": [],
            },
        )

    scraper = AsyncMock()
    scraper.search_listings.return_value = FAKE_LISTINGS

    bot = AsyncMock()

    app = MagicMock()
    app.bot_data = {
        "session_factory": factory,
        "scraper": scraper,
        "alert_min": 3,
    }
    app.bot = bot

    user_data: dict = {}

    yield factory, app, alert, bot, user_data, scraper


# ─── fixture para testes via wiz_confirm_cb ───


@pytest_asyncio.fixture
async def wizard_env():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    scraper = AsyncMock()
    scraper.search_listings.return_value = FAKE_LISTINGS

    bot = AsyncMock()

    app = MagicMock()
    app.bot_data = {
        "session_factory": factory,
        "scraper": scraper,
        "alert_min": 3,
    }
    app.bot = bot

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

    yield factory, update, context, scraper, query, bot


# ─── helpers ───


async def _await_seed_tasks(user_data: dict) -> None:
    """Aguarda todas as tasks de seed criadas em user_data."""
    for key, val in list(user_data.items()):
        if key.startswith("_seed_task_") and isinstance(val, asyncio.Task):
            await val


def _btn_labels(kb):
    """Extrai labels de todos os botões de um InlineKeyboardMarkup."""
    return [b.text for row in kb.inline_keyboard for b in row]


# ═══════════════════════════════════════════════════════════════
# Testes de immediate_seed (unidade)
# ═══════════════════════════════════════════════════════════════


async def test_seed_populates_seen_listings(seed_env):
    """Seed marca todos os OLX IDs como vistos no banco."""
    factory, app, alert, bot, user_data, scraper = seed_env

    await immediate_seed(app, alert.id, 99999, alert.filters, user_data)

    async with factory() as session:
        seen = await seen_olx_ids(session, alert.id)
    assert seen == {"111111111", "222222222"}


async def test_seed_sets_last_checked(seed_env):
    """Após seed, last_checked não deve ser None."""
    factory, app, alert, bot, user_data, scraper = seed_env

    await immediate_seed(app, alert.id, 99999, alert.filters, user_data)

    async with factory() as session:
        refreshed = await session.get(Alert, alert.id)
        assert refreshed.last_checked is not None


async def test_seed_sends_carousel_first_page(seed_env):
    """Seed envia o primeiro anúncio (com foto) via send_photo."""
    factory, app, alert, bot, user_data, scraper = seed_env

    await immediate_seed(app, alert.id, 99999, alert.filters, user_data)

    bot.send_photo.assert_called_once()
    call_kw = bot.send_photo.call_args[1]
    assert call_kw["chat_id"] == 99999
    assert "Apt 1" in call_kw["caption"]
    assert "1 de 2" in call_kw["caption"]
    assert "Página 1 de 1" in call_kw["caption"]


async def test_seed_stores_carousel_state(seed_env):
    """Seed armazena estado do carrossel em user_data."""
    factory, app, alert, bot, user_data, scraper = seed_env

    await immediate_seed(app, alert.id, 99999, alert.filters, user_data)

    key = f"carousel_{alert.id}"
    assert key in user_data
    carousel = user_data[key]
    assert len(carousel["listings"]) == 2
    assert carousel["index"] == 0
    assert carousel["transaction"] == "sale"
    assert carousel["page_size"] == PAGE_SIZE


async def test_seed_limits_to_max_carousel(seed_env):
    """immediate_seed limita a MAX_CAROUSEL anúncios."""
    factory, app, alert, bot, user_data, scraper = seed_env

    many = [
        {
            "olx_id": str(i) * 9,
            "title": f"Apt {i}",
            "price": 100000 * i,
            "url": f"https://olx.com.br/d/{str(i) * 9}",
            "thumbnail": None,
            "neighborhood": "Centro",
            "bedrooms": 2,
            "area_m2": 50,
        }
        for i in range(1, 10)
    ]
    scraper.search_listings.return_value = many

    await immediate_seed(app, alert.id, 99999, alert.filters, user_data)

    key = f"carousel_{alert.id}"
    assert len(user_data[key]["listings"]) == MAX_CAROUSEL


async def test_seed_no_listings_sends_empty_message(seed_env):
    """Sem anúncios, envia mensagem informando."""
    factory, app, alert, bot, user_data, scraper = seed_env
    scraper.search_listings.return_value = []

    await immediate_seed(app, alert.id, 99999, alert.filters, user_data)

    bot.send_message.assert_called_once()
    text = bot.send_message.call_args[1].get("text", "")
    assert "Nenhum" in text or "nenhum" in text


async def test_seed_fallback_on_scrape_failure(seed_env):
    """Se scraping falhar, envia aviso e NÃO seta last_checked."""
    factory, app, alert, bot, user_data, scraper = seed_env
    scraper.search_listings.side_effect = Exception("OLX bloqueou")

    await immediate_seed(app, alert.id, 99999, alert.filters, user_data)

    bot.send_message.assert_called_once()
    text = bot.send_message.call_args[1].get("text", "")
    assert "Não consegui" in text

    async with factory() as session:
        refreshed = await session.get(Alert, alert.id)
        assert refreshed.last_checked is None

    key = f"carousel_{alert.id}"
    assert key not in user_data


async def test_seed_text_fallback_when_no_thumbnail(seed_env):
    """Anúncio sem thumbnail envia send_message em vez de send_photo."""
    factory, app, alert, bot, user_data, scraper = seed_env
    scraper.search_listings.return_value = [
        {
            "olx_id": "333333333",
            "title": "Casa sem foto",
            "price": 200000,
            "url": "https://olx.com.br/d/333333333",
            "thumbnail": None,
            "neighborhood": "Farol",
            "bedrooms": 3,
            "area_m2": 90,
        }
    ]

    await immediate_seed(app, alert.id, 99999, alert.filters, user_data)

    bot.send_photo.assert_not_called()
    bot.send_message.assert_called_once()
    text = bot.send_message.call_args[1].get("text", "")
    assert "Casa sem foto" in text


# ═══════════════════════════════════════════════════════════════
# Testes de integração via wiz_confirm_cb
# ═══════════════════════════════════════════════════════════════


async def test_wizard_creates_seed_task(wizard_env):
    """wiz_confirm_cb cria uma task de seed em background."""
    factory, update, context, scraper, query, bot = wizard_env

    await wiz_confirm_cb(update, context)

    seed_tasks = {
        k: v
        for k, v in context.user_data.items()
        if k.startswith("_seed_task_")
    }
    assert len(seed_tasks) == 1


async def test_wizard_sends_loading_message(wizard_env):
    """wiz_confirm_cb envia '⏳ Peraê...' antes do seed."""
    factory, update, context, scraper, query, bot = wizard_env

    await wiz_confirm_cb(update, context)

    calls = query.message.reply_text.call_args_list
    texts = [c[0][0] if c[0] else c[1].get("text", "") for c in calls]
    assert any("Peraê" in t for t in texts)


async def test_wizard_populates_seen_after_seed(wizard_env):
    """Após await da task, seen_listings deve estar populado."""
    factory, update, context, scraper, query, bot = wizard_env

    await wiz_confirm_cb(update, context)
    await _await_seed_tasks(context.user_data)

    async with factory() as session:
        user = await get_or_create_user(session, 99999, "testuser")
        from database.crud import list_alerts

        alerts = await list_alerts(session, user.id)
        assert len(alerts) == 1
        seen = await seen_olx_ids(session, alerts[0].id)
    assert seen == {"111111111", "222222222"}


async def test_wizard_sets_last_checked_after_seed(wizard_env):
    """Após seed via wizard, last_checked deve ser preenchido."""
    factory, update, context, scraper, query, bot = wizard_env

    await wiz_confirm_cb(update, context)
    await _await_seed_tasks(context.user_data)

    async with factory() as session:
        user = await get_or_create_user(session, 99999, "testuser")
        from database.crud import list_alerts

        alerts = await list_alerts(session, user.id)
        assert alerts[0].last_checked is not None


async def test_wizard_carousel_sent_after_seed(wizard_env):
    """Após seed via wizard, bot.send_photo deve ter sido chamado (carrossel)."""
    factory, update, context, scraper, query, bot = wizard_env

    await wiz_confirm_cb(update, context)
    await _await_seed_tasks(context.user_data)

    assert bot.send_photo.called or bot.send_message.called


# ═══════════════════════════════════════════════════════════════
# Testes de formatação do carrossel
# ═══════════════════════════════════════════════════════════════


def test_carousel_caption_format():
    ad = {
        "title": "Apartamento 2q",
        "price": 250000,
        "bedrooms": 2,
        "area_m2": 65.0,
        "neighborhood": "Ponta Verde",
    }
    caption = _carousel_caption(ad, 0, 3, "sale")
    assert "Apartamento 2q" in caption
    assert "R$ 250.000" in caption
    assert "2 quartos" in caption
    assert "65m²" in caption
    assert "Ponta Verde" in caption
    assert "Venda" in caption
    assert "1 de 3" in caption
    assert "Página 1 de 1" in caption


def test_carousel_caption_multipage():
    """Contador mostra página correta para itens além da primeira página."""
    ad = {"title": "X", "price": 100000}
    caption = _carousel_caption(ad, 7, 12, "rent")
    assert "3 de 5" in caption
    assert "Página 2 de 3" in caption


def test_carousel_caption_last_partial_page():
    """Última página parcial mostra quantidade certa de itens."""
    ad = {"title": "X", "price": 100000}
    caption = _carousel_caption(ad, 10, 12, "sale")
    assert "1 de 2" in caption
    assert "Página 3 de 3" in caption


# ═══════════════════════════════════════════════════════════════
# Testes do teclado do carrossel
# ═══════════════════════════════════════════════════════════════


def test_keyboard_single_page_first():
    """Primeiro item, página única: sem Anterior, com Próximo, sem botões de página."""
    kb = _carousel_keyboard(carousel_id=1, index=0, total=3, url="https://olx.com.br/d/1")
    labels = _btn_labels(kb)
    assert "◀ Anterior" not in labels
    assert "Próximo ▶" in labels
    assert "◀ Página anterior" not in labels
    assert "⏭ Próxima página" not in labels
    assert "🔗 Ver anúncio" in labels
    assert "✅ Concluir" in labels


def test_keyboard_single_page_middle():
    """Item do meio, página única: com Anterior e Próximo, sem página."""
    kb = _carousel_keyboard(carousel_id=1, index=1, total=3, url="https://olx.com.br/d/1")
    labels = _btn_labels(kb)
    assert "◀ Anterior" in labels
    assert "Próximo ▶" in labels
    assert "◀ Página anterior" not in labels
    assert "⏭ Próxima página" not in labels


def test_keyboard_single_page_last():
    """Último item, página única: com Anterior, sem Próximo, sem página."""
    kb = _carousel_keyboard(carousel_id=1, index=2, total=3, url="https://olx.com.br/d/1")
    labels = _btn_labels(kb)
    assert "◀ Anterior" in labels
    assert "Próximo ▶" not in labels
    assert "⏭ Próxima página" not in labels


def test_keyboard_single_item():
    """Item único: apenas Ver anúncio e Concluir."""
    kb = _carousel_keyboard(carousel_id=1, index=0, total=1, url="https://olx.com.br/d/1")
    labels = _btn_labels(kb)
    assert "◀ Anterior" not in labels
    assert "Próximo ▶" not in labels
    assert "◀ Página anterior" not in labels
    assert "⏭ Próxima página" not in labels
    assert "🔗 Ver anúncio" in labels
    assert "✅ Concluir" in labels


def test_keyboard_multipage_first_page_first_item():
    """Primeiro item da primeira página com múltiplas: Próximo + Próxima página."""
    kb = _carousel_keyboard(carousel_id=1, index=0, total=12, url="https://olx.com.br/d/1")
    labels = _btn_labels(kb)
    assert "◀ Anterior" not in labels
    assert "Próximo ▶" in labels
    assert "◀ Página anterior" not in labels
    assert "⏭ Próxima página" in labels


def test_keyboard_multipage_first_page_last_item():
    """Último item da primeira página: Anterior + Próxima página, sem Próximo."""
    kb = _carousel_keyboard(carousel_id=1, index=4, total=12, url="https://olx.com.br/d/1")
    labels = _btn_labels(kb)
    assert "◀ Anterior" in labels
    assert "Próximo ▶" not in labels
    assert "◀ Página anterior" not in labels
    assert "⏭ Próxima página" in labels


def test_keyboard_multipage_middle_page():
    """Página do meio: ambos botões de página presentes."""
    kb = _carousel_keyboard(carousel_id=1, index=5, total=12, url="https://olx.com.br/d/1")
    labels = _btn_labels(kb)
    assert "◀ Página anterior" in labels
    assert "⏭ Próxima página" in labels


def test_keyboard_multipage_last_page():
    """Última página: Página anterior, sem Próxima página."""
    kb = _carousel_keyboard(carousel_id=1, index=10, total=12, url="https://olx.com.br/d/1")
    labels = _btn_labels(kb)
    assert "◀ Página anterior" in labels
    assert "⏭ Próxima página" not in labels
