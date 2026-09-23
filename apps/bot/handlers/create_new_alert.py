"""
Wizard multi-etapas para criar um alerta (comando ``/novo_alerta``).

Fluxo: KIND → CATEGORIES → PRICE → ROOMS → NEIGHBOURHOODS → NAME → CONFIRM.
Ao confirmar, grava o alerta direto no Postgres compartilhado (ADR 0005)
e busca matches.
"""

from __future__ import annotations

import logging
import re

from shared_models.tables import Listing, ListingKind
from telegram import CallbackQuery, Message, Update
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
    user_is_pro,
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
    ROOMS,
    CATEGORIES,
    NEIGHBOURHOODS,
    NAME,
    CONFIRM,
) = range(7)

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

_ROOMS_CALLBACKS: dict[str, int | None] = {
    "wiz_rooms_any": None,
    "wiz_rooms_1": 1,
    "wiz_rooms_2": 2,
    "wiz_rooms_3": 3,
    "wiz_rooms_4": 4,
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


def _allowed_categories(kind: ListingKind) -> set[str]:
    return {value for _, value, _ in keyboards.category_options_for_kind(kind)}


async def _show_choice(query: CallbackQuery, text: str) -> None:
    """Substitui a pergunta pela escolha e remove o teclado daquela mensagem."""
    await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN)
    await query.edit_message_reply_markup(reply_markup=None)


async def _enter_price(msg: Message, context: CustomContext) -> None:
    draft = _get_draft(context)
    kind = _draft_kind(draft)
    sent = await msg.reply_text(
        menus.wizard_preco_intro(listing_kind=kind),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=keyboards.price_range_keyboard(listing_kind=kind),
    )
    state = _get_wizard_state(context)
    state["price_prompt_chat_id"] = sent.chat_id
    state["price_prompt_message_id"] = sent.message_id


async def _edit_price_choice(context: CustomContext, draft: CreateAlertDraft) -> None:
    state = _get_wizard_state(context)
    chat_id = state.get("price_prompt_chat_id")
    message_id = state.get("price_prompt_message_id")
    if chat_id is None or message_id is None:
        return
    await context.bot.edit_message_text(
        chat_id=chat_id,
        message_id=message_id,
        text=menus.wizard_preco_escolhido(
            listing_kind=_draft_kind(draft),
            min_price=draft.get("min_price"),
            max_price=draft.get("max_price"),
        ),
        parse_mode=ParseMode.MARKDOWN,
    )


async def _enter_rooms(msg: Message) -> None:
    await msg.reply_text(
        menus.wizard_quartos_intro(),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=keyboards.rooms_keyboard(),
    )


async def _enter_categories(msg: Message, context: CustomContext) -> None:
    draft = _get_draft(context)
    sel = draft.get("categories", [])
    kind = _draft_kind(draft)
    await msg.reply_text(
        menus.wizard_categorias_intro(),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=keyboards.categories_keyboard(sel, listing_kind=kind),
    )


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

    await _show_choice(query, menus.wizard_tipo_escolhido(listing_kind=kind))
    await _enter_categories(update.effective_message, context)
    return CATEGORIES


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

    await _show_choice(
        query,
        menus.wizard_preco_escolhido(
            listing_kind=_draft_kind(draft),
            min_price=pmin,
            max_price=pmax,
        ),
    )
    await _enter_rooms(update.effective_message)
    return ROOMS


async def wiz_price_custom_cb(update: Update, context: CustomContext) -> int:
    query = update.callback_query
    assert query is not None
    await query.answer()
    draft = _get_draft(context)
    _get_wizard_state(context)["awaiting"] = "price_min"
    await _show_choice(
        query,
        menus.wizard_preco_personalizado(listing_kind=_draft_kind(draft)),
    )
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
    await _edit_price_choice(context, draft)
    await _enter_rooms(update.effective_message)
    return ROOMS


async def wiz_rooms_cb(update: Update, context: CustomContext) -> int:
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
    if query.data not in _ROOMS_CALLBACKS:
        return ROOMS
    draft["min_rooms"] = _ROOMS_CALLBACKS[query.data]

    await _show_choice(query, menus.wizard_quartos_escolhido(draft["min_rooms"]))
    await _enter_neighbourhoods(update.effective_message, context)
    return NEIGHBOURHOODS


async def wiz_categories_cb(update: Update, context: CustomContext) -> int:
    query = update.callback_query
    assert query is not None
    assert update.effective_message is not None
    assert context.user_data is not None
    await query.answer()

    if "create_alert_draft" not in context.user_data:
        await update.effective_message.reply_text("Sessão expirada. Use /novo_alerta novamente.")
        return ConversationHandler.END

    data = query.data or ""
    draft = _get_draft(context)
    kind = _draft_kind(draft)
    sel: list[str] = draft.setdefault("categories", [])

    if data == "wiz_cat_done":
        await _show_choice(query, menus.wizard_categorias_escolhido(sel))
        await _enter_price(update.effective_message, context)
        return PRICE

    if data.startswith("wiz_cat_"):
        slug = data.removeprefix("wiz_cat_")
        value = keyboards.category_value_for_slug(slug)
        if value is None or value not in _allowed_categories(kind):
            return CATEGORIES
        if value in sel:
            sel.remove(value)
        else:
            sel.append(value)
        draft["categories"] = sel

    await query.edit_message_text(
        menus.wizard_categorias_instrucao(sel),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=keyboards.categories_keyboard(sel, listing_kind=kind),
    )
    return CATEGORIES


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
        await _show_choice(query, menus.wizard_bairros_escolhido(sel))
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

    price_s = menus.price_range_label(draft.get("min_price"), draft.get("max_price"))

    await update.effective_message.reply_text(
        menus.confirmacao_resumo(
            price_s=price_s,
            nb_s=nb_s,
            name=name,
            listing_kind=_draft_kind(draft),
            min_rooms=draft.get("min_rooms"),
            categories=draft.get("categories"),
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
        alert_was_created = wizard_state.get("alert_was_created", True)
        if alert_id is None:
            result = await create_alert(
                chat_id=user.id,
                alert_name=draft["alert_name"],  # type: ignore[typeddict-item]
                min_price=draft.get("min_price"),
                max_price=draft.get("max_price"),
                neighbourhoods=draft.get("neighbourhoods", []),
                listing_kind=_draft_kind(draft),
                min_rooms=draft.get("min_rooms"),
                categories=draft.get("categories") or None,
            )
            if result.status == "cap_reached":
                wizard_state["confirming"] = False
                try:
                    pro = await user_is_pro(user.id)
                except Exception:
                    logger.exception("Falha ao checar Pro no cap de alerta")
                    pro = False
                await query.edit_message_text(
                    menus.alert_cap_reached(is_pro_user=pro),
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=(
                        keyboards.main_menu_keyboard()
                        if pro
                        else keyboards.alert_cap_upsell_keyboard()
                    ),
                )
                _clear_wizard(context)
                return ConversationHandler.END
            alert_id = result.alert_id
            alert_was_created = result.created
            draft["created_alert_id"] = alert_id
            wizard_state["alert_was_created"] = alert_was_created

        assert alert_id is not None

        if not wizard_state.get("seed_done"):
            await query.message.reply_text("⏳ Procurando imóveis que combinam com seu alerta…")  # type: ignore[union-attr]

            rows = await get_unnotified_listings(user.id)
            listings: list[Listing] = [row.listing for row in rows if row.alert_id == alert_id]

            if not listings:
                empty_msg = (
                    menus.seed_nenhum_imovel()
                    if alert_was_created
                    else menus.seed_alert_already_exists()
                )
                await query.message.reply_text(  # type: ignore[union-attr]
                    empty_msg,
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
                # Mark before follow-up UI so a later failure cannot re-notify.
                pairs = [(alert_id, item.listing_id) for item in listings]
                await mark_listings_notified(user.id, pairs)

                await query.message.reply_text(  # type: ignore[union-attr]
                    menus.seed_alert_created()
                    if alert_was_created
                    else menus.seed_alert_new_matches(),
                    reply_markup=keyboards.main_menu_keyboard(),
                )

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
            ROOMS: [
                CallbackQueryHandler(wiz_rooms_cb, pattern="^wiz_rooms_"),
            ],
            CATEGORIES: [
                CallbackQueryHandler(wiz_categories_cb, pattern="^wiz_cat_"),
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
