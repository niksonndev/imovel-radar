from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from handlers.home import present_message
from handlers.ui import menus


def test_present_message_edits_text_bubble() -> None:
    query = MagicMock()
    query.message = SimpleNamespace(photo=None, chat_id=11)
    query.edit_message_text = AsyncMock()
    query.delete_message = AsyncMock()
    context = MagicMock()
    context.bot.send_message = AsyncMock()

    asyncio.run(
        present_message(
            query,
            context,
            menus.menu_principal_inline(),
            reply_markup=None,
        )
    )

    query.edit_message_text.assert_awaited_once()
    query.delete_message.assert_not_called()
    context.bot.send_message.assert_not_called()


def test_present_message_keeps_photo_and_sends_new_text_menu() -> None:
    query = MagicMock()
    query.message = SimpleNamespace(photo=[object()], chat_id=42)
    query.edit_message_text = AsyncMock()
    query.edit_message_caption = AsyncMock()
    query.delete_message = AsyncMock()
    context = MagicMock()
    context.bot.send_message = AsyncMock()

    text = menus.menu_principal_inline()
    asyncio.run(present_message(query, context, text, reply_markup=None))

    query.delete_message.assert_not_called()
    query.edit_message_caption.assert_not_called()
    query.edit_message_text.assert_not_called()
    context.bot.send_message.assert_awaited_once()
    kwargs = context.bot.send_message.await_args.kwargs
    assert kwargs["chat_id"] == 42
    assert kwargs["text"] == text
