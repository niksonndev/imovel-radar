"""Wizard de criação de alerta (/novo_alerta) sem ConversationHandler."""

from __future__ import annotations

import logging
import re

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from bot.carousel import immediate_seed
from bot.ui import keyboards, menus
from database import create_new_alert, get_connection

logger = logging.getLogger(__name__)

NEW_ALERT_DRAFT_KEY = "new_alert_draft"
NEW_ALERT_STEP_KEY = "new_alert_step"

(
    WIZ_PRICE_MIN,
    WIZ_PRICE_MAX,
    WIZ_NEIGHBORHOODS,
    WIZ_CONFIRM,
    WIZ_NAME,
) = range(5)


def clear_wizard_state(context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data.pop(NEW_ALERT_DRAFT_KEY, None)
    context.user_data.pop(NEW_ALERT_STEP_KEY, None)


def _fmt_money(v: float | None) -> str:
    if v is None:
        return "—"
    return f"R$ {v:,.0f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _draft_or_none(context: ContextTypes.DEFAULT_TYPE) -> dict | None:
    draft = context.user_data.get(NEW_ALERT_DRAFT_KEY)
    if not isinstance(draft, dict):
        return None
    raw_nb = draft.get("neighbourhoods")
    if isinstance(raw_nb, set):
        draft["neighbourhoods"] = sorted(raw_nb)
    elif not isinstance(raw_nb, list):
        draft["neighbourhoods"] = list(raw_nb) if raw_nb else []
    return draft


async def novo_alerta_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Inicia o wizard de criação de alerta por comando."""
    context.user_data[NEW_ALERT_DRAFT_KEY] = {
        "alert_name": None,
        "min_price": None,
        "max_price": None,
        "neighbourhoods": [],
    }
    context.user_data[NEW_ALERT_STEP_KEY] = WIZ_PRICE_MIN
    await update.message.reply_text(
        menus.wizard_novo_alerta_intro(),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=keyboards.price_range_keyboard(),
    )


async def novo_alerta_entry_cb(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Inicia o wizard de criação de alerta via botão do menu."""
    q = update.callback_query
    await q.answer()
    context.user_data[NEW_ALERT_DRAFT_KEY] = {
        "alert_name": None,
        "min_price": None,
        "max_price": None,
        "neighbourhoods": [],
    }
    context.user_data[NEW_ALERT_STEP_KEY] = WIZ_PRICE_MIN
    await q.message.reply_text(
        menus.wizard_novo_alerta_intro(),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=keyboards.price_range_keyboard(),
    )


async def wiz_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Valida o nome do alerta e apresenta a tela de confirmação."""
    w = _draft_or_none(context)
    if w is None:
        clear_wizard_state(context)
        await update.message.reply_text(menus.wizard_sessao_expirada())
        return

    name = (update.message.text or "").strip()[:200]
    if not name:
        await update.message.reply_text(menus.wizard_nome_invalido())
        return

    w["alert_name"] = name

    sel = w.get("neighbourhoods") or []
    nb_s = ", ".join(sorted(sel)) if sel else "Qualquer bairro"

    pmin = w.get("min_price")
    pmax = w.get("max_price")
    if pmin is None and pmax is not None:
        price_s = f"Até {_fmt_money(pmax)}"
    elif pmin is not None and pmax is None:
        price_s = f"A partir de {_fmt_money(pmin)}"
    else:
        price_s = f"{_fmt_money(pmin)} - {_fmt_money(pmax)}"

    summary = menus.confirmacao_resumo(price_s=price_s, nb_s=nb_s, name=name)

    context.user_data[NEW_ALERT_STEP_KEY] = WIZ_CONFIRM
    await update.message.reply_text(
        summary,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=keyboards.alert_confirmation_keyboard(),
    )


async def wiz_price_preset_cb(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Callback dos botões de faixa comum e de "Personalizado"."""
    q = update.callback_query
    await q.answer()

    data = q.data or ""
    w = _draft_or_none(context)
    if w is None:
        clear_wizard_state(context)
        await q.message.reply_text(menus.wizard_sessao_expirada_curta())
        return

    if data == "wiz_price_custom":
        await q.message.reply_text(
            menus.wizard_personalizado_min(),
            parse_mode=ParseMode.MARKDOWN,
        )
        context.user_data[NEW_ALERT_STEP_KEY] = WIZ_PRICE_MIN
        return

    if not data.startswith("wiz_price_preset_"):
        return

    parts = data.split("_")
    if len(parts) < 5:
        return

    preset_tr = parts[-2]
    try:
        idx = int(parts[-1])
    except ValueError:
        idx = -1

    preset_map = {
        0: (None, 800),
        1: (800, 1500),
        2: (1500, 3000),
        3: (3000, None),
    }

    if preset_tr != "rent" or idx not in preset_map:
        return

    pmin, pmax = preset_map[idx]
    w["min_price"] = pmin
    w["max_price"] = pmax

    sel = w.get("neighbourhoods") or []
    await q.message.reply_text(
        menus.wizard_selecione_bairros(),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=keyboards.neighborhoods_keyboard(sel),
    )
    context.user_data[NEW_ALERT_STEP_KEY] = WIZ_NEIGHBORHOODS


async def wiz_price_min(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Lê e valida o preço mínimo informado no wizard."""
    w = _draft_or_none(context)
    if w is None:
        clear_wizard_state(context)
        await update.message.reply_text(menus.wizard_sessao_expirada())
        return

    text = (update.message.text or "").strip().lower()
    try:
        price_min = int(re.sub(r"\D", "", text) or 0)
    except Exception:
        price_min = 0
    if price_min <= 0:
        await update.message.reply_text(menus.wizard_preco_min_invalido())
        return

    w["min_price"] = price_min
    await update.message.reply_text(
        menus.wizard_preco_max_prompt(),
        parse_mode=ParseMode.MARKDOWN,
    )
    context.user_data[NEW_ALERT_STEP_KEY] = WIZ_PRICE_MAX


async def wiz_price_max(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Lê e valida o preço máximo antes de seguir para bairros."""
    w = _draft_or_none(context)
    if w is None:
        clear_wizard_state(context)
        await update.message.reply_text(menus.wizard_sessao_expirada())
        return

    text = (update.message.text or "").strip().lower()
    try:
        price_max = int(re.sub(r"\D", "", text) or 0)
    except Exception:
        price_max = 0
    if price_max <= 0:
        await update.message.reply_text(menus.wizard_preco_max_invalido())
        return

    p_min = w.get("min_price")
    if p_min is not None and price_max < p_min:
        await update.message.reply_text(menus.wizard_preco_max_menor_min())
        return

    w["max_price"] = price_max

    sel = w.get("neighbourhoods") or []
    await update.message.reply_text(
        menus.wizard_selecione_bairros_com_obs(),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=keyboards.neighborhoods_keyboard(sel),
    )
    context.user_data[NEW_ALERT_STEP_KEY] = WIZ_NEIGHBORHOODS


async def wiz_confirm_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Confirma ou cancela o alerta e executa seed inicial."""
    q = update.callback_query
    await q.answer()

    data = q.data or ""
    w = _draft_or_none(context)
    if w is None:
        clear_wizard_state(context)
        await q.message.reply_text(menus.wizard_sessao_expirada_curta())
        return

    if data == "wiz_confirm_no":
        clear_wizard_state(context)
        await q.message.reply_text(
            menus.wizard_nao_salvo(),
            reply_markup=keyboards.main_menu_keyboard(),
        )
        return

    if data != "wiz_confirm_yes":
        return

    name = w.get("alert_name")
    if not name:
        clear_wizard_state(context)
        await q.message.reply_text(
            menus.wizard_nome_ausente(),
            reply_markup=keyboards.main_menu_keyboard(),
        )
        return

    filters_dict = {
        "min_price": w.get("min_price"),
        "max_price": w.get("max_price"),
        "neighborhoods": sorted(w.get("neighbourhoods") or []),
    }

    conn = get_connection()
    try:
        alert_id = create_new_alert(conn, update.effective_user.id, w)
        conn.commit()
    except Exception:
        conn.rollback()
        logger.exception("Falha ao salvar novo alerta no banco.")
        await q.message.reply_text(
            menus.wizard_salvar_falha(),
            reply_markup=keyboards.main_menu_keyboard(),
        )
        clear_wizard_state(context)
        return
    finally:
        conn.close()

    clear_wizard_state(context)

    await q.message.reply_text(menus.wizard_seed_loading())
    await immediate_seed(
        context.application,
        alert_id,
        update.effective_user.id,
        filters_dict,
        context.user_data,
    )


async def wiz_neighborhoods_cb(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Alterna seleção de bairros e avança quando usuário conclui."""
    q = update.callback_query
    await q.answer()
    data = q.data or ""
    w = _draft_or_none(context)
    if w is None:
        clear_wizard_state(context)
        await q.message.reply_text(menus.wizard_sessao_expirada_curta())
        return

    sel: list[str] = w.setdefault("neighbourhoods", [])
    if data == "nbd_done":
        await q.message.reply_text(
            menus.wizard_nome_prompt(),
            parse_mode=ParseMode.MARKDOWN,
        )
        context.user_data[NEW_ALERT_STEP_KEY] = WIZ_NAME
        return
    if data.startswith("nbd_"):
        nb = data[4:]
        if nb in sel:
            sel.remove(nb)
        else:
            sel.append(nb)
        await q.edit_message_reply_markup(
            reply_markup=keyboards.neighborhoods_keyboard(sel)
        )


async def cancel_wiz(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Cancela o wizard atual e limpa dados temporários do usuário."""
    clear_wizard_state(context)
    await update.message.reply_text(
        menus.wizard_cancelado(),
        reply_markup=keyboards.main_menu_keyboard(),
    )
