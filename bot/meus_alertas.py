"""
Handler do menu *Meus Alertas*: lista alertas do usuário a partir do SQLite.
"""

from __future__ import annotations

import logging

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from bot.ui import keyboards, menus
from database import ensure_user, get_connection, list_alerts_for_user

logger = logging.getLogger(__name__)


async def meus_alertas_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Exibe alertas do usuário após toque em ``menu_meus_alertas``."""
    query = update.callback_query
    if query is None:
        return
    await query.answer()

    user = update.effective_user
    if user is None:
        return

    conn = get_connection()
    try:
        internal_user_id = ensure_user(conn, user.id)
        rows = list_alerts_for_user(conn, internal_user_id)
        alerts = [dict(row) for row in rows]
    except Exception:
        logger.exception("Falha ao listar alertas do usuário.")
        await query.edit_message_text(
            text=menus.meus_alertas_erro(),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboards.main_menu_keyboard(),
        )
        return
    finally:
        conn.close()

    await query.edit_message_text(
        text=menus.meus_alertas_view(alerts),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=keyboards.main_menu_keyboard(),
    )
