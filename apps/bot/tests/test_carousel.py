"""Tests for carousel helpers (stateless nav, slim cards, TTL prune)."""

from __future__ import annotations

import asyncio
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock

from handlers.carousel import (
    CAROUSEL_TTL_SECONDS,
    _carousel_keyboard,
    _listing_to_card,
    _parse_nav_callback,
    _photo_file_id,
    prune_expired_carousels,
    send_carousel,
)


def test_parse_nav_callback_absolute_index() -> None:
    assert _parse_nav_callback("crs_42_3") == ("42", 3)
    assert _parse_nav_callback("crs_alert-9_0") == ("alert-9", 0)
    assert _parse_nav_callback("crs_42_prev") is None
    assert _parse_nav_callback("menu_x") is None


def test_keyboard_encodes_target_index() -> None:
    kb = _carousel_keyboard("99", 1, 3, "https://example.com/ad", listing_id=1525220692)
    row = kb.inline_keyboard[0]
    assert row[0].callback_data == "crs_99_0"
    assert row[1].callback_data == "crs_99_2"
    actions = kb.inline_keyboard[1]
    assert actions[0].url == "https://example.com/ad"
    assert actions[1].callback_data == "wch_1525220692"


def test_watchlist_keyboard_uses_remove_action() -> None:
    kb = _carousel_keyboard(
        "wl42",
        0,
        1,
        "https://example.com/ad",
        listing_id=1525220692,
        mode="watchlist",
        watch_id=7,
    )
    actions = kb.inline_keyboard[0]
    assert actions[0].url == "https://example.com/ad"
    assert actions[1].callback_data == "wl_rm_7"


def test_listing_to_card_is_slim() -> None:
    listing = SimpleNamespace(
        title="Apt Centro",
        price_value=1500,
        neighbourhood="Pajuçara",
        url="https://olx.com.br/1",
        images=["https://img/1.jpg", "https://img/2.jpg"],
        properties={"rooms": 2, "size": 60.0, "real_estate_type": "Apartamento"},
        listing_id=1,
        active=True,
        first_seen_at="should-not-appear",
        updated_at="should-not-appear",
    )
    card = _listing_to_card(listing)  # type: ignore[arg-type]
    assert set(card) == {
        "listing_id",
        "title",
        "price_value",
        "neighbourhood",
        "url",
        "image_url",
        "file_id",
        "rooms",
        "size",
        "real_estate_type",
        "listing_active",
    }
    assert card["listing_id"] == 1
    assert card["image_url"] == "https://img/1.jpg"
    assert card["file_id"] is None
    assert card["listing_active"] is True
    assert "first_seen_at" not in card


def test_prune_expired_carousels() -> None:
    now = time.time()
    store: dict[str, object] = {
        "carousel_old": {"cards": [], "created_at": now - CAROUSEL_TTL_SECONDS - 10},
        "carousel_new": {"cards": [{"title": "x"}], "created_at": now},
        "other": {"keep": True},
    }
    assert prune_expired_carousels(store, now=now) == 1
    assert "carousel_old" not in store
    assert "carousel_new" in store
    assert store["other"] == {"keep": True}


def test_photo_file_id_from_message() -> None:
    msg = SimpleNamespace(photo=[SimpleNamespace(file_id="small"), SimpleNamespace(file_id="big")])
    assert _photo_file_id(msg) == "big"  # type: ignore[arg-type]
    assert _photo_file_id(True) is None
    assert _photo_file_id(None) is None


def test_send_carousel_stores_slim_cards_and_file_id() -> None:
    listing = SimpleNamespace(
        listing_id=99,
        title="Casa",
        price_value=2000,
        neighbourhood="Jatiúca",
        url="https://olx.com.br/2",
        images=["https://img/casa.jpg"],
        properties={"rooms": 3, "size": 80, "real_estate_type": "Casa"},
        active=True,
    )
    bot = AsyncMock()
    bot.send_photo = AsyncMock(
        return_value=SimpleNamespace(
            photo=[SimpleNamespace(file_id="tg-file-1")],
        )
    )
    store: dict[str, object] = {
        "carousel_stale": {
            "cards": [],
            "created_at": time.time() - CAROUSEL_TTL_SECONDS - 1,
        }
    }

    asyncio.run(send_carousel(bot, 7, [listing], "55", store))  # type: ignore[arg-type]

    assert "carousel_stale" not in store
    state = store["carousel_55"]
    assert isinstance(state, dict)
    assert "listings" not in state
    cards = state["cards"]
    assert len(cards) == 1
    assert cards[0]["file_id"] == "tg-file-1"
    assert cards[0]["image_url"] == "https://img/casa.jpg"
    assert isinstance(state["created_at"], float)
    bot.send_photo.assert_awaited_once()
    assert bot.send_photo.await_args.kwargs["photo"] == "https://img/casa.jpg"
