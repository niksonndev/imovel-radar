from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

from telegram.error import BadRequest

from handlers.ui import menus
from handlers.ui.loading import callback_needs_db_loading, show_db_loading


def test_db_loading_copy_has_hourglass() -> None:
    text = menus.db_loading()
    assert "⏳" in text
    assert "Carregando" in text


def test_callback_needs_db_loading_menu_and_detail() -> None:
    assert callback_needs_db_loading("menu_meus_alertas")
    assert callback_needs_db_loading("menu_watchlist")
    assert callback_needs_db_loading("mal_b")
    assert callback_needs_db_loading("mal_p_12")
    assert callback_needs_db_loading("mal_ed_3")
    assert callback_needs_db_loading("mal_rm_9")
    assert callback_needs_db_loading("wl_b")
    assert callback_needs_db_loading("wl_p_1")
    assert callback_needs_db_loading("wl_rm_4")
    assert callback_needs_db_loading("wl_confirm_yes")
    assert callback_needs_db_loading("email_pro_trial")
    assert callback_needs_db_loading("pro_subscribe")


def test_callback_needs_db_loading_excludes_nav_and_help() -> None:
    assert not callback_needs_db_loading(None)
    assert not callback_needs_db_loading("")
    assert not callback_needs_db_loading("menu_ajuda")
    assert not callback_needs_db_loading("mal_m")
    assert not callback_needs_db_loading("wl_m")
    assert not callback_needs_db_loading("wl_add")
    assert not callback_needs_db_loading("car_next_1")
    assert not callback_needs_db_loading("novo_alerta")


def test_show_db_loading_edits_message_without_answering() -> None:
    query = MagicMock()
    query.answer = AsyncMock()
    query.edit_message_text = AsyncMock()

    asyncio.run(show_db_loading(query))

    query.answer.assert_not_called()
    query.edit_message_text.assert_awaited_once()
    kwargs = query.edit_message_text.await_args
    assert kwargs.kwargs["text"] == menus.db_loading()
    assert kwargs.kwargs["reply_markup"] is None


def test_show_db_loading_swallows_bad_request() -> None:
    query = MagicMock()
    query.edit_message_text = AsyncMock(side_effect=BadRequest("Message is not modified"))

    asyncio.run(show_db_loading(query))
