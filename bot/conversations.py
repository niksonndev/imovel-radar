"""Wizard de criação de alerta (/novo_alerta)."""

from __future__ import annotations

import logging
import re

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from bot import keyboards
from bot.carousel import immediate_seed
from database import create_new_alert, get_connection

logger = logging.getLogger(__name__)

NEW_ALERT_DRAFT_KEY = "new_alert_draft"

(
    WIZ_PRICE_MIN,
    WIZ_PRICE_MAX,
    WIZ_NEIGHBORHOODS,
    WIZ_CONFIRM,
    WIZ_NAME,
) = range(5)


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


async def novo_alerta_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Inicia o wizard de criação de alerta por comando."""
    context.user_data[NEW_ALERT_DRAFT_KEY] = {
        "alert_name": None,
        "min_price": None,
        "max_price": None,
        "neighbourhoods": [],
    }
    await update.message.reply_text(
        "🆕 *Novo alerta (aluguel)*\n\nFaixa de preço — toque em uma opção ou *Personalizado*.",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=keyboards.price_range_keyboard(),
    )
    return WIZ_PRICE_MIN


async def novo_alerta_entry_cb(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Inicia o wizard de criação de alerta via botão do menu."""
    q = update.callback_query
    await q.answer()
    context.user_data[NEW_ALERT_DRAFT_KEY] = {
        "alert_name": None,
        "min_price": None,
        "max_price": None,
        "neighbourhoods": [],
    }
    await q.message.reply_text(
        "🆕 *Novo alerta (aluguel)*\n\nFaixa de preço — toque em uma opção ou *Personalizado*.",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=keyboards.price_range_keyboard(),
    )
    return WIZ_PRICE_MIN


async def wiz_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Valida o nome do alerta e apresenta a tela de confirmação."""
    w = _draft_or_none(context)
    if w is None:
        await update.message.reply_text(
            "Sua sessão do wizard expirou. Use /novo_alerta novamente."
        )
        return ConversationHandler.END

    name = (update.message.text or "").strip()[:200]
    if not name:
        await update.message.reply_text("Nome inválido. Tente de novo.")
        return WIZ_NAME

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

    summary = (
        "🧾 *Confirmação do alerta*\n\n"
        f"💰 *Preço:* {price_s}\n"
        f"📍 *Bairros:* {nb_s}\n"
        f"📝 *Nome:* `{name}`\n\n"
        "Confirme abaixo:"
    )

    await update.message.reply_text(
        summary,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=keyboards.alert_confirmation_keyboard(),
    )
    return WIZ_CONFIRM


async def wiz_price_preset_cb(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """
    Callback dos botões de faixa comum e de "Personalizado".

    Presets: keyboards.price_range_keyboard() — wiz_price_preset_rent_<idx>, wiz_price_custom
    """
    q = update.callback_query
    await q.answer()

    data = q.data or ""
    w = _draft_or_none(context)
    if w is None:
        await q.message.reply_text("Sessão expirada. Use /novo_alerta novamente.")
        return ConversationHandler.END

    if data == "wiz_price_custom":
        await q.message.reply_text(
            "Personalizado: envie o *preço mínimo* (R$, só número).",
            parse_mode=ParseMode.MARKDOWN,
        )
        return WIZ_PRICE_MIN

    if not data.startswith("wiz_price_preset_"):
        return WIZ_PRICE_MIN

    parts = data.split("_")
    if len(parts) < 5:
        return WIZ_PRICE_MIN

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
        return WIZ_PRICE_MIN

    pmin, pmax = preset_map[idx]
    w["min_price"] = pmin
    w["max_price"] = pmax

    sel = w.get("neighbourhoods") or []
    await q.message.reply_text(
        "Selecione os *bairros* (toque para marcar). Depois: Concluir.",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=keyboards.neighborhoods_keyboard(sel),
    )
    return WIZ_NEIGHBORHOODS


async def wiz_price_min(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Lê e valida o preço mínimo informado no wizard."""
    w = _draft_or_none(context)
    if w is None:
        await update.message.reply_text(
            "Sua sessão do wizard expirou. Use /novo_alerta novamente."
        )
        return ConversationHandler.END

    text = (update.message.text or "").strip().lower()
    try:
        price_min = int(re.sub(r"\D", "", text) or 0)
    except Exception:
        price_min = 0
    if price_min <= 0:
        await update.message.reply_text("Número inválido. Ex.: 150000")
        return WIZ_PRICE_MIN

    w["min_price"] = price_min
    await update.message.reply_text(
        "Preço *máximo* (R$):", parse_mode=ParseMode.MARKDOWN
    )
    return WIZ_PRICE_MAX


async def wiz_price_max(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Lê e valida o preço máximo antes de seguir para bairros."""
    w = _draft_or_none(context)
    if w is None:
        await update.message.reply_text(
            "Sua sessão do wizard expirou. Use /novo_alerta novamente."
        )
        return ConversationHandler.END

    text = (update.message.text or "").strip().lower()
    try:
        price_max = int(re.sub(r"\D", "", text) or 0)
    except Exception:
        price_max = 0
    if price_max <= 0:
        await update.message.reply_text("Número inválido.")
        return WIZ_PRICE_MAX

    p_min = w.get("min_price")
    if p_min is not None and price_max < p_min:
        await update.message.reply_text(
            "O preço máximo deve ser maior ou igual ao mínimo."
        )
        return WIZ_PRICE_MAX

    w["max_price"] = price_max

    sel = w.get("neighbourhoods") or []
    await update.message.reply_text(
        "Selecione os *bairros* (toque para marcar). Depois: Concluir.\n"
        "Se não quiser filtrar por bairro, conclua sem marcar.",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=keyboards.neighborhoods_keyboard(sel),
    )
    return WIZ_NEIGHBORHOODS


async def wiz_confirm_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Confirma ou cancela o alerta e executa seed inicial."""
    q = update.callback_query
    await q.answer()

    data = q.data or ""
    w = _draft_or_none(context)
    if w is None:
        await q.message.reply_text("Sessão expirada. Use /novo_alerta novamente.")
        return ConversationHandler.END

    if data == "wiz_confirm_no":
        context.user_data.pop(NEW_ALERT_DRAFT_KEY, None)
        await q.message.reply_text(
            "Ok! O alerta não foi salvo.",
            reply_markup=keyboards.main_menu_keyboard(),
        )
        return ConversationHandler.END

    if data != "wiz_confirm_yes":
        return WIZ_CONFIRM

    name = w.get("alert_name")
    if not name:
        context.user_data.pop(NEW_ALERT_DRAFT_KEY, None)
        await q.message.reply_text(
            "Nome do alerta ausente. Tente novamente pelo menu principal.",
            reply_markup=keyboards.main_menu_keyboard(),
        )
        return ConversationHandler.END

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
            "Não consegui salvar seu alerta agora. Tente novamente em instantes.",
            reply_markup=keyboards.main_menu_keyboard(),
        )
        context.user_data.pop(NEW_ALERT_DRAFT_KEY, None)
        return ConversationHandler.END
    finally:
        conn.close()

    context.user_data.pop(NEW_ALERT_DRAFT_KEY, None)

    await q.message.reply_text("⏳ Peraê, tô procurando imóveis pra você...")
    await immediate_seed(
        context.application,
        alert_id,
        update.effective_user.id,
        filters_dict,
        context.user_data,
    )

    return ConversationHandler.END


async def wiz_neighborhoods_cb(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Alterna seleção de bairros e avança quando usuário conclui."""
    q = update.callback_query
    await q.answer()
    data = q.data or ""
    w = _draft_or_none(context)
    if w is None:
        await q.message.reply_text("Sessão expirada. Use /novo_alerta novamente.")
        return ConversationHandler.END

    sel: list[str] = w.setdefault("neighbourhoods", [])
    if data == "nbd_done":
        await q.message.reply_text(
            "Agora, envie o *nome do alerta* (ex.: `Aluguel Centro`).",
            parse_mode=ParseMode.MARKDOWN,
        )
        return WIZ_NAME
    if data.startswith("nbd_"):
        nb = data[4:]
        if nb in sel:
            sel.remove(nb)
        else:
            sel.append(nb)
        await q.edit_message_reply_markup(
            reply_markup=keyboards.neighborhoods_keyboard(sel)
        )
    return WIZ_NEIGHBORHOODS


async def cancel_wiz(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancela o wizard atual e limpa dados temporários do usuário."""
    context.user_data.pop(NEW_ALERT_DRAFT_KEY, None)
    await update.message.reply_text(
        "Criação de alerta cancelada.",
        reply_markup=keyboards.main_menu_keyboard(),
    )
    return ConversationHandler.END

def conversation_novo_alerta() -> ConversationHandler:
    """Monta e retorna o ConversationHandler do fluxo /novo_alerta."""
    return ConversationHandler(
        entry_points=[
            CommandHandler("novo_alerta", novo_alerta_entry),
            CallbackQueryHandler(novo_alerta_entry_cb, pattern=r"^menu_novo_alerta$"),
        ],
        states={
            WIZ_PRICE_MIN: [
                CallbackQueryHandler(wiz_price_preset_cb, pattern=r"^wiz_price_"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, wiz_price_min),
            ],
            WIZ_PRICE_MAX: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, wiz_price_max)
            ],
            WIZ_NEIGHBORHOODS: [
                CallbackQueryHandler(wiz_neighborhoods_cb, pattern=r"^nbd_")
            ],
            WIZ_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, wiz_name)],
            WIZ_CONFIRM: [
                CallbackQueryHandler(wiz_confirm_cb, pattern=r"^wiz_confirm_")
            ],
        },
        fallbacks=[CommandHandler("cancelar", cancel_wiz)],
        name="novo_alerta_wiz",
    )
