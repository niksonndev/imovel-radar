"""
Wizard multi-etapas para criar um alerta (comando ``/novo_alerta``).

Fluxo: KIND (Comprar/Alugar) → PRICE → NEIGHBOURHOODS → NAME → CONFIRM.
Ao confirmar, grava o alerta direto no Postgres compartilhado (ADR 0005)
e busca matches.
"""

from __future__ import annotations

import logging
import re

from shared_models.tables import Listing, ListingKind
from shared_models.utils import format_brl
from telegram import Message, Update
from telegram.constants import ParseMode
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    filters,
)

from handlers.carousel import send_carousel
from handlers.data import (
    create_alert,
    get_neighbourhoods,
    get_unnotified_listings,
    mark_listings_notified,
)
from handlers.ui import keyboards, menus
from models import (
    CreateAlertDraft,
    CreateAlertWizardState,
    CustomContext,
)

logger = logging.getLogger(__name__)

(
    KIND,
    PRICE,
    NEIGHBOURHOODS,
    NAME,
    CONFIRM,
) = range(5)

_RENT_PRESETS = {
    "wiz_price_preset_rent_0": (0, 800),
    "wiz_price_preset_rent_1": (800, 1500),
    "wiz_price_preset_rent_2": (1500, 3000),
    "wiz_price_preset_rent_3": (3000, 999_999),
}
_SALE_PRESETS = {
    "wiz_price_preset_sale_0": (0, 150_000),
    "wiz_price_preset_sale_1": (150_000, 300_000),
    "wiz_price_preset_sale_2": (300_000, 500_000),
    "wiz_price_preset_sale_3": (500_000, 99_999_999),
}


def _get_draft(context: CustomContext) -> CreateAlertDraft:
    assert context.user_data is not None
    assert "create_alert_draft" in context.user_data
    return context.user_data["create_alert_draft"]


def _get_wizard_state(context: CustomContext) -> CreateAlertWizardState:
    assert context.user_data is not None
    assert "create_alert_wizard_state" in context.user_data
    return context.user_data["create_alert_wizard_state"]


def _draft_kind(draft: CreateAlertDraft) -> ListingKind:
    kind = draft.get("listing_kind")
    return "venda" if kind == "venda" else "aluguel"


async def _enter_neighbourhoods(msg: Message, context: CustomContext) -> None:
    draft = _get_draft(context)
    wizard_state = _get_wizard_state(context)
    sel = draft.get("neighbourhoods", [])
    kind = _draft_kind(draft)

    try:
        nb_options = await get_neighbourhoods(listing_kind=kind)
        wizard_state["neighbourhood_options"] = nb_options
    except Exception:
        logger.exception("Falha ao buscar bairros do scraper")
        await msg.reply_text("Erro ao carregar bairros. Tente novamente.")
        return

    wizard_state["neighbourhood_page"] = 0
    await msg.reply_text(
        menus.wizard_bairros_instrucao(sel),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=keyboards.neighborhoods_keyboard(sel, nb_options, page=0),
    )


async def new_alert_cmd(update: Update, context: CustomContext) -> int:
    assert context.user_data is not None
    assert update.effective_message is not None

    context.user_data["create_alert_draft"] = CreateAlertDraft()
    context.user_data["create_alert_wizard_state"] = CreateAlertWizardState()

    # Entry via callback (menu) — answer and clear orphan keyboard if present.
    if update.callback_query is not None:
        await update.callback_query.answer()
        try:
            await update.callback_query.edit_message_reply_markup(reply_markup=None)
        except Exception:
            pass

    await update.effective_message.reply_text(
        menus.wizard_novo_alerta_intro(),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=keyboards.listing_kind_keyboard(),
    )
    return KIND


async def wiz_kind_cb(update: Update, context: CustomContext) -> int:
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
    kind: ListingKind = "venda" if query.data == "wiz_kind_venda" else "aluguel"
    draft["listing_kind"] = kind

    await query.edit_message_reply_markup(reply_markup=None)
    await update.effective_message.reply_text(
        menus.wizard_preco_intro(listing_kind=kind),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=keyboards.price_range_keyboard(listing_kind=kind),
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
    preset_map = {**_RENT_PRESETS, **_SALE_PRESETS}
    pmin, pmax = preset_map.get(query.data, (0, 999_999))
    draft["min_price"] = pmin
    draft["max_price"] = pmax

    await query.edit_message_reply_markup(reply_markup=None)
    await _enter_neighbourhoods(update.effective_message, context)
    return NEIGHBOURHOODS


async def wiz_price_custom_cb(update: Update, context: CustomContext) -> int:
    query = update.callback_query
    assert query is not None
    await query.answer()
    await query.edit_message_reply_markup(reply_markup=None)
    _get_wizard_state(context)["awaiting"] = "price_min"
    await query.message.reply_text("Digite o preço mínimo (só números):")  # type: ignore[union-attr]
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

    if "neighbourhood_options" not in wizard_state:
        await query.message.reply_text(  # type: ignore[union-attr]
            "Sessão expirada. Use /novo_alerta novamente.",
            reply_markup=keyboards.main_menu_keyboard(),
        )
        return ConversationHandler.END

    nb_options = wizard_state.get("neighbourhood_options") or []
    n_nb = len(nb_options)
    psize = keyboards.NEIGHBORHOODS_PAGE_SIZE
    total_pages = max(1, (n_nb + psize - 1) // psize) if n_nb else 1
    cur_page = max(0, min(wizard_state.get("neighbourhood_page", 0), total_pages - 1))
    wizard_state["neighbourhood_page"] = cur_page

    if data == "nbd_done":
        wizard_state.pop("neighbourhood_options", None)
        wizard_state.pop("neighbourhood_page", None)
        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text(  # type: ignore[union-attr]
            menus.wizard_nome_prompt(),
            parse_mode=ParseMode.MARKDOWN,
        )
        return NAME

    if data == "nbd_pg_prev":
        if cur_page > 0:
            wizard_state["neighbourhood_page"] = cur_page - 1
        await query.edit_message_text(
            menus.wizard_bairros_instrucao(sel),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboards.neighborhoods_keyboard(
                sel, nb_options, page=wizard_state["neighbourhood_page"]
            ),
        )
        return NEIGHBOURHOODS

    if data == "nbd_pg_next":
        if cur_page < total_pages - 1:
            wizard_state["neighbourhood_page"] = cur_page + 1
        await query.edit_message_text(
            menus.wizard_bairros_instrucao(sel),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboards.neighborhoods_keyboard(
                sel, nb_options, page=wizard_state["neighbourhood_page"]
            ),
        )
        return NEIGHBOURHOODS

    if data == "nbd_pg_info":
        return NEIGHBOURHOODS

    if data.startswith("nbd_"):
        try:
            idx = int(data.removeprefix("nbd_"))
        except ValueError:
            return NEIGHBOURHOODS
        if 0 <= idx < len(nb_options):
            name = nb_options[idx]
            if name in sel:
                sel.remove(name)
            else:
                sel.append(name)
            draft["neighbourhoods"] = sel

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
        menus.confirmacao_resumo(
            price_s=price_s,
            nb_s=nb_s,
            name=name,
            listing_kind=_draft_kind(draft),
        ),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=keyboards.alert_confirmation_keyboard(),
    )
    return CONFIRM


def _clear_wizard(context: CustomContext) -> None:
    assert context.user_data is not None
    context.user_data.pop("create_alert_draft", None)
    context.user_data.pop("create_alert_wizard_state", None)


async def wiz_confirm_cb(update: Update, context: CustomContext) -> int:
    query = update.callback_query
    assert query is not None
    assert update.effective_user is not None
    assert context.user_data is not None
    await query.answer()

    if query.data == "wiz_confirm_no":
        _clear_wizard(context)
        await query.message.reply_text(  # type: ignore[union-attr]
            "Okay — alerta não salvo.",
            reply_markup=keyboards.main_menu_keyboard(),
        )
        return ConversationHandler.END

    if "create_alert_draft" not in context.user_data:
        await query.message.reply_text(  # type: ignore[union-attr]
            "Este alerta já foi salvo (ou a sessão expirou).",
            reply_markup=keyboards.main_menu_keyboard(),
        )
        return ConversationHandler.END

    draft = _get_draft(context)
    wizard_state = _get_wizard_state(context)
    if wizard_state.get("confirming"):
        return CONFIRM
    wizard_state["confirming"] = True

    user = update.effective_user
    try:
        alert_id = draft.get("created_alert_id")
        if alert_id is None:
            alert_id = await create_alert(
                chat_id=user.id,
                alert_name=draft["alert_name"],  # type: ignore[typeddict-item]
                min_price=draft.get("min_price"),
                max_price=draft.get("max_price"),
                neighbourhoods=draft["neighbourhoods"],  # type: ignore[typeddict-item]
                listing_kind=_draft_kind(draft),
            )
            draft["created_alert_id"] = alert_id

        if not wizard_state.get("seed_done"):
            await query.message.reply_text("⏳ Procurando imóveis que combinam com seu alerta…")  # type: ignore[union-attr]

            rows = await get_unnotified_listings(user.id)
            listings: list[Listing] = [row.listing for row in rows if row.alert_id == alert_id]

            if not listings:
                await query.message.reply_text(  # type: ignore[union-attr]
                    menus.seed_nenhum_imovel(),
                    reply_markup=keyboards.main_menu_keyboard(),
                )
            else:
                await send_carousel(
                    context.application.bot,
                    user.id,
                    listings,
                    str(alert_id),
                    context.application.bot_data,
                )

                await query.message.reply_text(  # type: ignore[union-attr]
                    menus.seed_alert_created(),
                    reply_markup=keyboards.main_menu_keyboard(),
                )
                pairs = [(alert_id, item.listing_id) for item in listings]
                await mark_listings_notified(user.id, pairs)

            wizard_state["seed_done"] = True

    except Exception:
        wizard_state["confirming"] = False
        logger.exception("Falha ao salvar alerta no banco")
        await query.message.reply_text(  # type: ignore[union-attr]
            "Não foi possível salvar o alerta. Tente novamente.",
            reply_markup=keyboards.main_menu_keyboard(),
        )
        return ConversationHandler.END

    _clear_wizard(context)
    return ConversationHandler.END


async def cancel_wiz(update: Update, context: CustomContext) -> int:
    assert update.effective_message is not None
    _clear_wizard(context)
    await update.effective_message.reply_text(
        "Criação do alerta cancelada.",
        reply_markup=keyboards.main_menu_keyboard(),
    )
    return ConversationHandler.END


async def start_fallback(update: Update, context: CustomContext) -> int:
    """``/start`` durante o wizard: encerra a conversa e mostra o menu."""
    assert update.effective_message is not None
    _clear_wizard(context)
    await update.effective_message.reply_text(
        menus.start_welcome(),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=keyboards.main_menu_keyboard(),
    )
    return ConversationHandler.END


def new_alert_conversation() -> ConversationHandler:
    return ConversationHandler(
        name="new_alert",
        persistent=True,
        allow_reentry=True,
        entry_points=[
            CommandHandler("novo_alerta", new_alert_cmd),
            CallbackQueryHandler(new_alert_cmd, pattern="^novo_alerta$"),
        ],
        states={
            KIND: [
                CallbackQueryHandler(wiz_kind_cb, pattern="^wiz_kind_(aluguel|venda)$"),
            ],
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
        fallbacks=[
            CommandHandler("cancelar", cancel_wiz),
            CommandHandler("start", start_fallback),
        ],
    )
