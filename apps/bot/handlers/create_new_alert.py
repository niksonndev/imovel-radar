"""
Wizard multi-etapas para criar um alerta de aluguel (comando ``/novo_alerta``).

Ao confirmar, chama a API do scraper para criar o alerta e buscar matches.
"""

from __future__ import annotations

import json
import logging
import re

from telegram import Message, Update
from telegram.constants import ParseMode
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    filters,
)
from telegram.helpers import escape_markdown

from handlers.api_client import ScraperAPI
from handlers.carousel import send_carousel
from handlers.ui import keyboards, menus
from models import (
    CreateAlertDraft,
    CreateAlertWizardState,
    CustomContext,
)
from shared_models import HydratedListing
from shared_models.api_schemas import CreateAlertRequest
from shared_models.utils import format_brl

logger = logging.getLogger(__name__)

(
    PRICE,
    NEIGHBOURHOODS,
    NAME,
    CONFIRM,
) = range(4)


def _get_draft(context: CustomContext) -> CreateAlertDraft:
    assert context.user_data is not None
    assert "create_alert_draft" in context.user_data
    return context.user_data["create_alert_draft"]


def _get_wizard_state(context: CustomContext) -> CreateAlertWizardState:
    assert context.user_data is not None
    assert "create_alert_wizard_state" in context.user_data
    return context.user_data["create_alert_wizard_state"]


async def _enter_neighbourhoods(msg: Message, context: CustomContext) -> None:
    draft = _get_draft(context)
    wizard_state = _get_wizard_state(context)
    sel = draft.get("neighbourhoods", [])

    api = ScraperAPI()
    try:
        response = await api.get_neighbourhoods()
        nb_options = response.neighbourhoods
        wizard_state["neighbourhood_options"] = nb_options
    except Exception:
        logger.exception("Falha ao buscar bairros do scraper")
        await msg.reply_text("Erro ao carregar bairros. Tente novamente.")
        return
    finally:
        await api.close()

    wizard_state["neighbourhood_page"] = 0
    await msg.reply_text(
        menus.wizard_bairros_instrucao(sel),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=keyboards.neighborhoods_keyboard(sel, nb_options, page=0),
    )


def _confirm_summary(*, price_s: str, nb_s: str, name: str) -> str:
    esc_price = escape_markdown(price_s, version=1)
    esc_nb = escape_markdown(nb_s, version=1)
    esc_name = escape_markdown(name, version=1)
    return (
        "🧾 *Configuração do alerta*\n\n"
        f"💰 *Preço:* {esc_price}\n"
        f"📍 *Bairros:* {esc_nb}\n"
        f"📝 *Nome:* `{esc_name}`\n\n"
        "Confirme abaixo:"
    )


async def new_alert_cmd(update: Update, context: CustomContext) -> int:
    assert context.user_data is not None
    assert update.effective_message is not None

    context.user_data["create_alert_draft"] = CreateAlertDraft()
    context.user_data["create_alert_wizard_state"] = CreateAlertWizardState()

    await update.effective_message.reply_text(
        menus.wizard_novo_alerta_intro(),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=keyboards.price_range_keyboard(),
    )
    return PRICE


async def wiz_price_preset_cb(update: Update, context: CustomContext) -> int:
    assert update.effective_message is not None
    assert update.callback_query is not None
    assert context.user_data is not None

    query = update.callback_query
    await query.answer()

    if "create_alert_draft" not in context.user_data:
        await update.effective_message.reply_text("Sessão expirada. Use /novo_alerta novamente.")
        return ConversationHandler.END

    draft = _get_draft(context)
    assert query.data is not None
    preset_map = {
        "wiz_price_preset_rent_0": (0, 800),
        "wiz_price_preset_rent_1": (800, 1500),
        "wiz_price_preset_rent_2": (1500, 3000),
        "wiz_price_preset_rent_3": (3000, 999_999),
    }
    pmin, pmax = preset_map.get(query.data, (0, 999_999))
    draft["min_price"] = pmin
    draft["max_price"] = pmax

    await _enter_neighbourhoods(update.effective_message, context)
    return NEIGHBOURHOODS


async def wiz_price_custom_cb(update: Update, context: CustomContext) -> int:
    query = update.callback_query
    assert query is not None
    await query.answer()
    _get_wizard_state(context)["awaiting"] = "price_min"
    await query.message.reply_text("Digite o preço mínimo (só números):")
    return PRICE


async def wiz_price_text(update: Update, context: CustomContext) -> int:
    assert update.effective_message is not None
    draft = _get_draft(context)
    wizard_state = _get_wizard_state(context)
    value = int(re.sub(r"\D", "", update.effective_message.text or "") or 0)
    if value <= 0:
        await update.effective_message.reply_text("Número inválido, tente novamente.")
        return PRICE

    if wizard_state.get("awaiting") == "price_min":
        draft["min_price"] = value
        wizard_state["awaiting"] = "price_max"
        await update.effective_message.reply_text("Agora o preço máximo:")
        return PRICE

    pmin = draft.get("min_price")
    if isinstance(pmin, int) and value < pmin:
        await update.effective_message.reply_text(
            "O preço máximo deve ser maior ou igual ao mínimo. Envie o máximo novamente:"
        )
        return PRICE

    draft["max_price"] = value
    wizard_state.pop("awaiting", None)
    await _enter_neighbourhoods(update.effective_message, context)
    return NEIGHBOURHOODS


async def wiz_neighbourhoods_cb(update: Update, context: CustomContext) -> int:
    query = update.callback_query
    assert query is not None
    await query.answer()
    data = query.data or ""
    draft = _get_draft(context)
    wizard_state = _get_wizard_state(context)
    sel: list[str] = draft.setdefault("neighbourhoods", [])

    if data == "nbd_done":
        wizard_state.pop("neighbourhood_options", None)
        wizard_state.pop("neighbourhood_page", None)
        await query.message.reply_text(
            "Agora envie o *nome do alerta* (ex: `Aluguel Jatiúca`).",
            parse_mode=ParseMode.MARKDOWN,
        )
        return NAME

    if data == "nbd_pg_info":
        return NEIGHBOURHOODS

    nb_options = wizard_state.get("neighbourhood_options") or []
    n_nb = len(nb_options)
    psize = keyboards.NEIGHBORHOODS_PAGE_SIZE
    total_pages = max(1, (n_nb + psize - 1) // psize) if n_nb else 1
    cur_page = max(0, min(wizard_state.get("neighbourhood_page", 0), total_pages - 1))
    wizard_state["neighbourhood_page"] = cur_page

    if data == "nbd_pg_prev":
        if cur_page > 0:
            wizard_state["neighbourhood_page"] = cur_page - 1
        await query.edit_message_reply_markup(
            reply_markup=keyboards.neighborhoods_keyboard(
                sel, nb_options, page=wizard_state["neighbourhood_page"]
            )
        )
        return NEIGHBOURHOODS

    if data == "nbd_pg_next":
        if cur_page < total_pages - 1:
            wizard_state["neighbourhood_page"] = cur_page + 1
        await query.edit_message_reply_markup(
            reply_markup=keyboards.neighborhoods_keyboard(
                sel, nb_options, page=wizard_state["neighbourhood_page"]
            )
        )
        return NEIGHBOURHOODS

    idx_s = data[4:]  # após "nbd_"
    try:
        idx = int(idx_s, 10)
    except ValueError:
        return NEIGHBOURHOODS
    if not (0 <= idx < len(nb_options)):
        return NEIGHBOURHOODS

    nb = nb_options[idx]
    if nb in sel:
        sel.remove(nb)
    else:
        sel.append(nb)

    await query.edit_message_text(
        menus.wizard_bairros_instrucao(sel),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=keyboards.neighborhoods_keyboard(
            sel, nb_options, page=wizard_state["neighbourhood_page"]
        ),
    )
    return NEIGHBOURHOODS


async def wiz_name(update: Update, context: CustomContext) -> int:
    assert update.effective_message is not None
    draft = _get_draft(context)

    name = (update.effective_message.text or "").strip()[:200]
    if not name:
        await update.effective_message.reply_text("Nome inválido, tente novamente.")
        return NAME

    draft["alert_name"] = name

    sel = draft.get("neighbourhoods", [])
    nb_s = ", ".join(sorted(sel)) if sel else "Qualquer bairro"

    pmin = draft.get("min_price")
    pmax = draft.get("max_price")
    if pmin is None:
        price_s = f"Até {format_brl(pmax)}"
    elif pmax is None:
        price_s = f"A partir de {format_brl(pmin)}"
    else:
        price_s = f"{format_brl(pmin)} – {format_brl(pmax)}"

    await update.effective_message.reply_text(
        _confirm_summary(price_s=price_s, nb_s=nb_s, name=name),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=keyboards.alert_confirmation_keyboard(),
    )
    return CONFIRM


async def wiz_confirm_cb(update: Update, context: CustomContext) -> int:
    query = update.callback_query
    assert query is not None
    assert update.effective_user is not None
    await query.answer()
    draft = _get_draft(context)

    if query.data == "wiz_confirm_no":
        await query.message.reply_text(
            "Okay — alerta não salvo.",
            reply_markup=keyboards.main_menu_keyboard(),
        )
        return ConversationHandler.END

    user = update.effective_user
    api = ScraperAPI()
    try:
        req = CreateAlertRequest(
            user_id=user.id,
            alert_name=draft["alert_name"],
            min_price=draft["min_price"],
            max_price=draft["max_price"],
            neighbourhoods=json.dumps(draft["neighbourhoods"]),
        )
        response = await api.create_alert(req)
        alert_id = response.id

        await query.message.reply_text("⏳ Procurando imóveis que combinam com seu alerta…")

        # Fetch matches
        matches_resp = await api.get_matches(alert_id)
        matches = matches_resp.matches

        if not matches:
            await query.message.reply_text(
                menus.seed_nenhum_imovel(),
                reply_markup=keyboards.main_menu_keyboard(),
            )
        else:
            await send_carousel(
                context.application.bot,
                user.id,
                matches,
                str(alert_id),
                context.application.bot_data,
            )
            await query.message.reply_text(
                menus.seed_alert_created(),
                reply_markup=keyboards.main_menu_keyboard(),
            )

        # Mark matches as notified
        if matches:
            await api.mark_notified(alert_id, [m.list_id for m in matches])

    except Exception:
        logger.exception("Falha ao criar alerta via API")
        await query.message.reply_text(
            "Não foi possível salvar o alerta. Tente novamente.",
            reply_markup=keyboards.main_menu_keyboard(),
        )
        return ConversationHandler.END
    finally:
        await api.close()

    return ConversationHandler.END


async def cancel_wiz(update: Update, context: CustomContext) -> int:
    assert context.user_data is not None
    assert update.effective_message is not None
    context.user_data.pop("create_alert_draft", None)
    context.user_data.pop("create_alert_wizard_state", None)
    await update.effective_message.reply_text(
        "Criação do alerta cancelada.",
        reply_markup=keyboards.main_menu_keyboard(),
    )
    return ConversationHandler.END


def new_alert_conversation() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            CommandHandler("novo_alerta", new_alert_cmd),
            CallbackQueryHandler(new_alert_cmd, pattern="^novo_alerta$"),
        ],
        states={
            PRICE: [
                CallbackQueryHandler(wiz_price_preset_cb, pattern="^wiz_price_preset_"),
                CallbackQueryHandler(wiz_price_custom_cb, pattern="^wiz_price_custom$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, wiz_price_text),
            ],
            NEIGHBOURHOODS: [
                CallbackQueryHandler(wiz_neighbourhoods_cb, pattern="^nbd_"),
            ],
            NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, wiz_name),
            ],
            CONFIRM: [
                CallbackQueryHandler(wiz_confirm_cb, pattern="^wiz_confirm_"),
            ],
        },
        fallbacks=[CommandHandler("cancelar", cancel_wiz)],
    )