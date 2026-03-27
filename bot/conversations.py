"""Wizard de criação de alerta (/novo_alerta)."""

from __future__ import annotations

import logging
import json
import re
from datetime import datetime

from telegram import Update
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
from database import get_connection

logger = logging.getLogger(__name__)

(
    WIZ_TRANSACTION,
    WIZ_PRICE_MIN,
    WIZ_PRICE_MAX,
    WIZ_NEIGHBORHOODS,
    WIZ_CONFIRM,
    WIZ_NAME,
) = range(6)


def _fmt_money(v: float | None) -> str:
    if v is None:
        return "—"
    return f"R$ {v:,.0f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _wizard_or_none(context: ContextTypes.DEFAULT_TYPE) -> dict | None:
    wizard = context.user_data.get("wizard_alert")
    if not isinstance(wizard, dict):
        return None
    return wizard


def _persist_alert(chat_id: int, wizard: dict) -> int:
    """Cria usuário (se necessário) e persiste o alerta no SQLite."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("INSERT OR IGNORE INTO users (chat_id) VALUES (?);", (chat_id,))
        cur.execute("SELECT id FROM users WHERE chat_id = ?;", (chat_id,))
        row = cur.fetchone()
        if row is None:
            raise RuntimeError("Não foi possível identificar o usuário no banco.")

        user_id = int(row["id"])
        neighborhoods = sorted(wizard.get("neighborhoods_selected") or set())
        neighbourhood = ", ".join(neighborhoods) if neighborhoods else None
        max_price = wizard.get("price_max")
        category = json.dumps(
            {
                "name": wizard.get("name"),
                "transaction": wizard.get("transaction", "sale"),
                "price_min": wizard.get("price_min"),
                "price_max": wizard.get("price_max"),
                "neighborhoods": neighborhoods,
            },
            ensure_ascii=False,
        )

        cur.execute(
            """
            INSERT INTO alerts (user_id, neighbourhood, max_price, category, active, created_at)
            VALUES (?, ?, ?, ?, 1, ?);
            """,
            (
                user_id,
                neighbourhood,
                max_price,
                category,
                datetime.utcnow().replace(microsecond=0).isoformat(),
            ),
        )
        conn.commit()
        return int(cur.lastrowid)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


async def novo_alerta_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["wizard_alert"] = {"neighborhoods_selected": set()}
    await update.message.reply_text(
        "🆕 *Configurando novo alerta*\n\nVocê quer:\nAlugar ou Comprar?",
        parse_mode="Markdown",
        reply_markup=keyboards.transaction_keyboard(),
    )
    return WIZ_TRANSACTION


async def novo_alerta_entry_cb(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    q = update.callback_query
    await q.answer()
    context.user_data["wizard_alert"] = {"neighborhoods_selected": set()}
    await q.message.reply_text(
        "🆕 *Novo alerta*\n\nTipo:\nAluguel ou Venda",
        parse_mode="Markdown",
        reply_markup=keyboards.transaction_keyboard(),
    )
    return WIZ_TRANSACTION


async def wiz_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    w = _wizard_or_none(context)
    if w is None:
        await update.message.reply_text(
            "Sessão do wizard expirada. Use /novo_alerta novamente."
        )
        return ConversationHandler.END

    name = (update.message.text or "").strip()[:200]
    if not name:
        await update.message.reply_text("Nome inválido. Tente de novo.")
        return WIZ_NAME

    w["name"] = name

    tr_label = {"sale": "Venda", "rent": "Aluguel"}.get(
        w.get("transaction"), w.get("transaction")
    )

    sel = w.get("neighborhoods_selected") or set()
    nb_s = ", ".join(sorted(sel)) if sel else "Qualquer bairro"

    pmin = w.get("price_min")
    pmax = w.get("price_max")
    if pmin is None and pmax is not None:
        price_s = f"Até {_fmt_money(pmax)}"
    elif pmin is not None and pmax is None:
        price_s = f"A partir de {_fmt_money(pmin)}"
    else:
        price_s = f"{_fmt_money(pmin)} - {_fmt_money(pmax)}"

    summary = (
        "🧾 *Confirmação do alerta*\n\n"
        f"💳 *Tipo:* {tr_label}\n"
        f"💰 *Preço:* {price_s}\n"
        f"📍 *Bairros:* {nb_s}\n"
        f"📝 *Nome:* `{name}`\n\n"
        "Confirme abaixo:"
    )

    await update.message.reply_text(
        summary,
        parse_mode="Markdown",
        reply_markup=keyboards.alert_confirmation_keyboard(),
    )
    return WIZ_CONFIRM


async def wiz_transaction_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    q = update.callback_query
    await q.answer()
    w = _wizard_or_none(context)
    if w is None:
        await q.message.reply_text("Sessão expirada. Use /novo_alerta novamente.")
        return ConversationHandler.END

    key = q.data.replace("wiz_tr_", "")
    w["transaction"] = key
    await q.edit_message_text(
        "Faixa de preço:\n\nSelecione uma opção (ou use *Personalizado*).",
        parse_mode="Markdown",
        reply_markup=keyboards.price_range_keyboard(key),
    )
    return WIZ_PRICE_MIN


async def wiz_price_preset_cb(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """
    Callback dos botões de faixa comum e de "Personalizado".

    Presets são gerados por keyboards.price_range_keyboard() com callback_data:
      - wiz_price_preset_<rent|sale>_<idx>
      - wiz_price_custom
    """
    q = update.callback_query
    await q.answer()

    data = q.data or ""
    w = _wizard_or_none(context)
    if w is None:
        await q.message.reply_text("Sessão expirada. Use /novo_alerta novamente.")
        return ConversationHandler.END

    if data == "wiz_price_custom":
        await q.message.reply_text(
            "Personalizado: envie o *preço mínimo* (R$, só número).",
            parse_mode="Markdown",
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
        "rent": {
            0: (None, 800),
            1: (800, 1500),
            2: (1500, 3000),
            3: (3000, None),
        },
        "sale": {
            0: (None, 150000),
            1: (150000, 300000),
            2: (300000, 600000),
            3: (600000, None),
        },
    }

    if preset_tr not in preset_map or idx not in preset_map[preset_tr]:
        return WIZ_PRICE_MIN

    pmin, pmax = preset_map[preset_tr][idx]
    w["price_min"] = pmin
    w["price_max"] = pmax

    sel = w.get("neighborhoods_selected") or set()
    await q.message.reply_text(
        "Selecione os *bairros* (toque para marcar). Depois: Concluir.",
        parse_mode="Markdown",
        reply_markup=keyboards.neighborhoods_keyboard(sel),
    )
    return WIZ_NEIGHBORHOODS


async def wiz_price_min(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    w = _wizard_or_none(context)
    if w is None:
        await update.message.reply_text(
            "Sessão do wizard expirada. Use /novo_alerta novamente."
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

    w["price_min"] = price_min
    await update.message.reply_text("Preço *máximo* (R$):", parse_mode="Markdown")
    return WIZ_PRICE_MAX


async def wiz_price_max(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    w = _wizard_or_none(context)
    if w is None:
        await update.message.reply_text(
            "Sessão do wizard expirada. Use /novo_alerta novamente."
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

    price_min = w.get("price_min")
    if price_min is not None and price_max < price_min:
        await update.message.reply_text(
            "O preço máximo deve ser maior ou igual ao mínimo."
        )
        return WIZ_PRICE_MAX

    w["price_max"] = price_max

    sel = w.get("neighborhoods_selected") or set()
    await update.message.reply_text(
        "Selecione os *bairros* (toque para marcar). Depois: Concluir.\n"
        "Se não quiser filtrar por bairro, conclua sem marcar.",
        parse_mode="Markdown",
        reply_markup=keyboards.neighborhoods_keyboard(sel),
    )
    return WIZ_NEIGHBORHOODS


async def wiz_confirm_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    q = update.callback_query
    await q.answer()

    data = q.data or ""
    w = _wizard_or_none(context)
    if w is None:
        await q.message.reply_text("Sessão expirada. Use /novo_alerta novamente.")
        return ConversationHandler.END

    if data == "wiz_confirm_no":
        context.user_data.pop("wizard_alert", None)
        await q.message.reply_text(
            "Ok! O alerta não foi salvo.",
            reply_markup=keyboards.main_menu_keyboard(),
        )
        return ConversationHandler.END

    if data != "wiz_confirm_yes":
        return WIZ_CONFIRM

    name = w.get("name")
    if not name:
        context.user_data.pop("wizard_alert", None)
        await q.message.reply_text(
            "Nome do alerta ausente. Tente novamente pelo menu.",
            reply_markup=keyboards.main_menu_keyboard(),
        )
        return ConversationHandler.END

    filters_dict = {
        "transaction": w.get("transaction", "sale"),
        "price_min": w.get("price_min"),
        "price_max": w.get("price_max"),
        "neighborhoods": sorted(w.get("neighborhoods_selected") or set()),
    }

    try:
        alert_id = _persist_alert(update.effective_user.id, w)
    except Exception:
        logger.exception("Falha ao salvar novo alerta no banco.")
        await q.message.reply_text(
            "Não consegui salvar seu alerta agora. Tente novamente em instantes.",
            reply_markup=keyboards.main_menu_keyboard(),
        )
        context.user_data.pop("wizard_alert", None)
        return ConversationHandler.END

    context.user_data.pop("wizard_alert", None)

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
    q = update.callback_query
    await q.answer()
    data = q.data or ""
    w = _wizard_or_none(context)
    if w is None:
        await q.message.reply_text("Sessão expirada. Use /novo_alerta novamente.")
        return ConversationHandler.END

    sel = w.setdefault("neighborhoods_selected", set())
    if data == "nbd_done":
        await q.message.reply_text(
            "Agora, envie o *nome do alerta* (ex.: `Aluguel Centro`).",
            parse_mode="Markdown",
        )
        return WIZ_NAME
    if data.startswith("nbd_"):
        name = data[4:]
        if name in sel:
            sel.discard(name)
        else:
            sel.add(name)
        await q.edit_message_reply_markup(
            reply_markup=keyboards.neighborhoods_keyboard(sel)
        )
    return WIZ_NEIGHBORHOODS


async def cancel_wiz(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.pop("wizard_alert", None)
    await update.message.reply_text(
        "Criação de alerta cancelada.",
        reply_markup=keyboards.main_menu_keyboard(),
    )
    return ConversationHandler.END

def conversation_novo_alerta() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            CommandHandler("novo_alerta", novo_alerta_entry),
            CallbackQueryHandler(novo_alerta_entry_cb, pattern=r"^menu_novo_alerta$"),
        ],
        states={
            WIZ_TRANSACTION: [
                CallbackQueryHandler(wiz_transaction_cb, pattern=r"^wiz_tr_")
            ],
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
        persistent=False,
    )
