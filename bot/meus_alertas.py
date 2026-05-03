"""
Handlers do menu *Meus Alertas*: listagem, detalhe, remoção e stub de edição.
"""

from __future__ import annotations

import logging
import re

from telegram import CallbackQuery, Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from bot.ui import keyboards, menus
from database import (
    delete_alert_for_user,
    ensure_user,
    get_alert_for_user,
    get_connection,
    list_alerts_for_user,
)

logger = logging.getLogger(__name__)

MAL_PICK_RE = re.compile(r"^mal_p_(\d+)$")
MAL_ED_RE = re.compile(r"^mal_ed_(\d+)$")
MAL_RM_RE = re.compile(r"^mal_rm_(\d+)$")


async def _render_alert_list_message(
    query: CallbackQuery, telegram_user_id: int
) -> None:
    """Atualiza a mensagem com a listagem e o teclado de escolha (sem ``answer``)."""
    conn = get_connection()
    try:
        internal_user_id = ensure_user(conn, telegram_user_id)
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

    text, visible = menus.meus_alertas_list_message(alerts)
    markup = (
        keyboards.meus_alertas_pick_keyboard(visible)
        if visible
        else keyboards.meus_alertas_empty_keyboard()
    )
    await query.edit_message_text(
        text=text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=markup,
    )


async def meus_alertas_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Abre a listagem a partir do botão *Meus Alertas* do menu principal."""
    query = update.callback_query
    if query is None:
        return
    await query.answer()

    user = update.effective_user
    if user is None:
        return

    await _render_alert_list_message(query, user.id)


async def meus_alertas_actions_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Roteia ``mal_*``: menu principal, lista, detalhe, edição (stub), remoção."""
    query = update.callback_query
    if query is None:
        return
    user = update.effective_user
    if user is None:
        return

    data = query.data or ""
    telegram_user_id = user.id

    if data == "mal_m":
        await query.answer()
        await query.edit_message_text(
            text=menus.menu_principal_inline(),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboards.main_menu_keyboard(),
        )
        return

    if data == "mal_b":
        await query.answer()
        await _render_alert_list_message(query, telegram_user_id)
        return

    m_pick = MAL_PICK_RE.match(data)
    if m_pick is not None:
        alert_id = int(m_pick.group(1))
        await query.answer()
        conn = get_connection()
        try:
            internal_user_id = ensure_user(conn, telegram_user_id)
            row = get_alert_for_user(conn, alert_id, internal_user_id)
        except Exception:
            logger.exception("Falha ao carregar alerta (detalhe).")
            await query.answer("Não foi possível abrir o alerta.", show_alert=True)
            return
        finally:
            conn.close()

        if row is None:
            await query.answer("Alerta não encontrado.", show_alert=True)
            await _render_alert_list_message(query, telegram_user_id)
            return

        alert = dict(row)
        await query.edit_message_text(
            text=menus.meus_alertas_detail_view(alert),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboards.meus_alertas_detail_keyboard(alert_id),
        )
        return

    m_ed = MAL_ED_RE.match(data)
    if m_ed is not None:
        alert_id = int(m_ed.group(1))
        await query.answer()
        conn = get_connection()
        try:
            internal_user_id = ensure_user(conn, telegram_user_id)
            row = get_alert_for_user(conn, alert_id, internal_user_id)
        except Exception:
            logger.exception("Falha ao carregar alerta (edição).")
            await query.answer("Não foi possível abrir o alerta.", show_alert=True)
            return
        finally:
            conn.close()

        if row is None:
            await query.answer("Alerta não encontrado.", show_alert=True)
            await _render_alert_list_message(query, telegram_user_id)
            return

        alert = dict(row)
        await query.edit_message_text(
            text=menus.meus_alertas_editar_stub(alert),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboards.meus_alertas_edit_stub_keyboard(alert_id),
        )
        return

    m_rm = MAL_RM_RE.match(data)
    if m_rm is not None:
        alert_id = int(m_rm.group(1))
        conn = get_connection()
        try:
            internal_user_id = ensure_user(conn, telegram_user_id)
            deleted = delete_alert_for_user(conn, alert_id, internal_user_id)
            conn.commit()
        except Exception:
            conn.rollback()
            logger.exception("Falha ao remover alerta.")
            await query.answer("Não foi possível remover o alerta.", show_alert=True)
            return
        finally:
            conn.close()

        if not deleted:
            await query.answer("Alerta não encontrado.", show_alert=True)
            await _render_alert_list_message(query, telegram_user_id)
            return

        await query.answer("Alerta removido.")
        await _render_alert_list_message(query, telegram_user_id)
        return

    logger.warning("Callback mal_* não reconhecido: %s", data)
    await query.answer()
