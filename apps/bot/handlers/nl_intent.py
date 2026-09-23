"""
Tratamento do onboarding em linguagem natural (estado INTENT).

Converte texto livre em filtros para CreateAlertDraft, pergunta apenas
o que faltar (cidade, tipo ou preço) e gera o nome do alerta automaticamente.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from telegram import Message, Update
from telegram.constants import ParseMode
from telegram.ext import ConversationHandler

import config
from handlers.data import get_neighbourhoods
from handlers.ui import keyboards, menus
from infrastructure.ai.alert_extractor import extract_alert_intent, match_neighbourhoods
from models import CreateAlertDraft, CreateAlertWizardState, CustomContext

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


def _get_draft(context: CustomContext) -> CreateAlertDraft:
    assert context.user_data is not None
    return context.user_data.setdefault("create_alert_draft", {})


def _get_wizard_state(context: CustomContext) -> CreateAlertWizardState:
    assert context.user_data is not None
    return context.user_data.setdefault("create_alert_wizard_state", {})


def _format_k(val: int) -> str:
    """Formata valores em milhares/milhões de forma amigável."""
    if val >= 1_000_000:
        v = val / 1_000_000
        formatted = f"{v:.1f}M".replace(".0M", "M").replace(".", ",")
        return f"{formatted}"
    if val >= 1000 and val % 1000 == 0:
        return f"{val // 1000} mil"
    return f"{val:,}".replace(",", ".")


def auto_alert_name(draft: CreateAlertDraft) -> str:
    """Gera nome automático e conciso para o alerta a partir dos critérios."""
    # 1. Categoria
    cats = draft.get("categories") or []
    if len(cats) == 1:
        c = cats[0]
        if c == "Apartamentos":
            cat_label = "Apto"
        elif c == "Casas":
            cat_label = "Casa"
        elif c == "Aluguel de quartos":
            cat_label = "Quarto"
        else:
            cat_label = c
    else:
        cat_label = "Imóvel"

    # 2. Localização (Bairros ou Cidade)
    nbs = draft.get("neighbourhoods") or []
    if len(nbs) == 1:
        loc_label = nbs[0]
    elif len(nbs) == 2:
        loc_label = f"{nbs[0]} e {nbs[1]}"
    elif len(nbs) > 2:
        loc_label = f"{nbs[0]} e +{len(nbs) - 1}"
    else:
        loc_label = draft.get("municipality", "Maceió")

    # 3. Preço
    min_p = draft.get("min_price")
    max_p = draft.get("max_price")
    price_label = ""
    if max_p is not None and min_p is not None and min_p > 0:
        price_label = f"R$ {_format_k(min_p)}–{_format_k(max_p)}"
    elif max_p is not None:
        price_label = f"até R$ {_format_k(max_p)}"
    elif min_p is not None:
        price_label = f"a partir de R$ {_format_k(min_p)}"

    parts = [p for p in (cat_label, loc_label, price_label) if p]
    name = " · ".join(parts)
    return name[:120]


async def advance_nl_flow(update: Update, context: CustomContext) -> int:
    """Avança o fluxo de linguagem natural perguntando apenas o que falta.

    Se todos os campos mandatórios (cidade, tipo e preço) estiverem preenchidos,
    gera o nome automático e vai direto para a tela de confirmação (CONFIRM).
    """
    from handlers.create_new_alert import CITY, CONFIRM, KIND, PRICE

    draft = _get_draft(context)
    wizard_state = _get_wizard_state(context)

    msg = update.effective_message
    if msg is None:
        return ConversationHandler.END

    # 1. Falta a cidade?
    if not draft.get("municipality"):
        await msg.reply_text(
            menus.wizard_nl_falta_cidade(),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboards.city_keyboard(),
        )
        return CITY

    # 2. Se a cidade agora é conhecida e tínhamos bairros pendentes, faz o match
    raw_nbs = wizard_state.pop("pending_raw_neighbourhoods", None)
    if raw_nbs and not draft.get("neighbourhoods"):
        try:
            available = await get_neighbourhoods(
                municipality=draft.get("municipality", "Maceió"),
                listing_kind=draft.get("listing_kind"),
            )
            draft["neighbourhoods"] = match_neighbourhoods(raw_nbs, available)
        except Exception:
            logger.exception("Falha ao buscar bairros para matching NL")

    # 3. Falta o tipo de transação (aluguel / venda)?
    if not draft.get("listing_kind"):
        await msg.reply_text(
            menus.wizard_nl_falta_tipo(),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboards.listing_kind_keyboard(),
        )
        return KIND

    # 4. Falta o preço (pelo menos um limite é obrigatório)?
    if draft.get("min_price") is None and draft.get("max_price") is None:
        kind = draft.get("listing_kind", "aluguel")
        city = draft.get("municipality", "Maceió")
        sent = await msg.reply_text(
            menus.wizard_nl_falta_preco(listing_kind=kind),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboards.price_range_keyboard(
                listing_kind=kind,
                municipality=city,
            ),
        )
        wizard_state["price_prompt_chat_id"] = sent.chat_id
        wizard_state["price_prompt_message_id"] = sent.message_id
        return PRICE

    # 5. Tudo preenchido! Gera o nome do alerta e vai direto à confirmação
    name = draft.get("alert_name") or auto_alert_name(draft)
    draft["alert_name"] = name

    sel = draft.get("neighbourhoods", [])
    nb_s = ", ".join(sorted(sel)) if sel else "Qualquer bairro"
    price_s = menus.price_range_label(draft.get("min_price"), draft.get("max_price"))

    await msg.reply_text(
        menus.confirmacao_resumo(
            price_s=price_s,
            nb_s=nb_s,
            name=name,
            listing_kind=draft.get("listing_kind", "aluguel"),
            municipality=draft.get("municipality", "Maceió"),
            min_rooms=draft.get("min_rooms"),
            categories=draft.get("categories"),
        ),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=keyboards.alert_confirmation_keyboard(),
    )
    return CONFIRM


async def wiz_nl_text(update: Update, context: CustomContext) -> int:
    """Recebe a mensagem em texto livre do usuário e processa a extração."""
    from handlers.create_new_alert import CITY, INTENT

    assert update.effective_message is not None
    text = (update.effective_message.text or "").strip()
    if not text:
        await update.effective_message.reply_text(
            menus.wizard_nl_texto_vazio(),
            reply_markup=keyboards.nl_prompt_keyboard(),
        )
        return INTENT

    draft = _get_draft(context)
    wizard_state = _get_wizard_state(context)

    try:
        if update.effective_chat:
            await update.effective_chat.send_action("typing")
    except Exception:
        pass

    extracted = await extract_alert_intent(
        text,
        provider=config.LLM_PROVIDER,
        api_key=config.resolve_openai_api_key(),
        model=config.LLM_MODEL,
        timeout_s=config.LLM_TIMEOUT_SECONDS,
    )

    if extracted is None:
        logger.info("Extração NL não identificou intenção; caindo no wizard de botões")
        wizard_state["nl_mode"] = False
        await update.effective_message.reply_text(
            menus.wizard_cidade_intro(),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboards.city_keyboard(),
        )
        return CITY

    wizard_state["nl_mode"] = True

    if extracted.municipality in {"Maceió", "Recife", "Natal"}:
        draft["municipality"] = extracted.municipality

    if extracted.listing_kind in {"aluguel", "venda"}:
        draft["listing_kind"] = extracted.listing_kind

    if extracted.categories:
        valid_cats = [
            c for c in extracted.categories if c in {"Apartamentos", "Casas", "Aluguel de quartos"}
        ]
        if valid_cats:
            draft["categories"] = valid_cats

    if extracted.min_price is not None and extracted.min_price > 0:
        draft["min_price"] = extracted.min_price

    if extracted.max_price is not None and extracted.max_price > 0:
        draft["max_price"] = extracted.max_price

    if extracted.min_rooms is not None and extracted.min_rooms > 0:
        draft["min_rooms"] = extracted.min_rooms

    if extracted.neighbourhoods:
        city = draft.get("municipality")
        if city:
            try:
                available = await get_neighbourhoods(
                    municipality=city,
                    listing_kind=draft.get("listing_kind"),
                )
                draft["neighbourhoods"] = match_neighbourhoods(
                    extracted.neighbourhoods, available
                )
            except Exception:
                logger.exception("Falha ao buscar bairros para match inicial")
        else:
            wizard_state["pending_raw_neighbourhoods"] = extracted.neighbourhoods

    return await advance_nl_flow(update, context)


async def wiz_nl_buttons_cb(update: Update, context: CustomContext) -> int:
    """Usuário optou por configurar através dos botões tradicionais."""
    from handlers.create_new_alert import CITY

    query = update.callback_query
    assert query is not None
    await query.answer()

    wizard_state = _get_wizard_state(context)
    wizard_state["nl_mode"] = False

    try:
        await query.edit_message_reply_markup(reply_markup=None)
    except Exception:
        pass

    target_msg = update.effective_message
    if target_msg is None and isinstance(query.message, Message):
        target_msg = query.message
    if target_msg is not None:
        await target_msg.reply_text(
            menus.wizard_cidade_intro(),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboards.city_keyboard(),
        )
    return CITY
