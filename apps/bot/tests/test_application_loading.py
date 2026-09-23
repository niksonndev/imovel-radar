from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

from telegram import Update

from application import RadarApplication


def test_process_update_shows_loading_before_ensure_user() -> None:
    order: list[str] = []

    async def fake_loading(query) -> None:
        order.append("loading")

    async def fake_ensure(chat_id: int) -> bool:
        order.append("ensure")
        return True

    async def fake_super(self, update: object) -> None:
        order.append("handlers")

    query = MagicMock()
    query.data = "menu_meus_alertas"
    user = MagicMock()
    user.id = 42
    update = MagicMock(spec=Update)
    update.callback_query = query
    update.effective_user = user

    app = MagicMock(spec=RadarApplication)
    app.process_update = RadarApplication.process_update.__get__(app, RadarApplication)

    with (
        patch("application.show_db_loading", side_effect=fake_loading),
        patch("application.ensure_user", side_effect=fake_ensure),
        patch.object(RadarApplication.__mro__[1], "process_update", fake_super),
    ):
        asyncio.run(app.process_update(update))

    assert order == ["loading", "ensure", "handlers"]


def test_process_update_skips_loading_for_help() -> None:
    order: list[str] = []

    async def fake_loading(query) -> None:
        order.append("loading")

    async def fake_ensure(chat_id: int) -> bool:
        order.append("ensure")
        return True

    async def fake_super(self, update: object) -> None:
        order.append("handlers")

    query = MagicMock()
    query.data = "menu_ajuda"
    user = MagicMock()
    user.id = 42
    update = MagicMock(spec=Update)
    update.callback_query = query
    update.effective_user = user

    app = MagicMock(spec=RadarApplication)
    app.process_update = RadarApplication.process_update.__get__(app, RadarApplication)

    with (
        patch("application.show_db_loading", side_effect=fake_loading),
        patch("application.ensure_user", side_effect=fake_ensure),
        patch.object(RadarApplication.__mro__[1], "process_update", fake_super),
    ):
        asyncio.run(app.process_update(update))

    assert order == ["ensure", "handlers"]
