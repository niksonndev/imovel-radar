"""Menu principal e roteamento de callbacks de navegação.

Callbacks antigos ``mal_m`` / ``wl_m`` continuam válidos para mensagens já
enviadas. Destinos de menu são reencaminhados daqui quando um
``ConversationHandler`` precisa encerrar o fluxo e ainda honrar o clique.
"""

from __future__ import annotations

import logging

from telegram import CallbackQuery, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.error import BadRequest

from handlers.ui import keyboards, menus
from models import CustomContext

logger = logging.getLogger(__name__)

# Cliques de menu que devem abortar um wizard e ir para o destino.
MENU_NAV_CALLBACK_RE = (
    r"^(?:menu_home|mal_m|wl_m|menu_meus_alertas|menu_watchlist|menu_ajuda)$"
)


async def show_main_menu(update: Update, context: CustomContext) -> None:
    """Mostra o menu principal. Saindo de um card, a foto fica e o menu é novo."""
    query = update.callback_query
    if query is None:
        return
    await query.answer()
    await _present_main_menu(query, context)


async def present_message(
    query: CallbackQuery,
    context: CustomContext,
    text: str,
    *,
    reply_markup: InlineKeyboardMarkup | None = None,
    parse_mode: str | None = ParseMode.MARKDOWN,
) -> None:
    """Mostra um menu de texto.

    Bolha de texto: edita o corpo. Card de foto: a imagem permanece e o menu
    abre numa mensagem nova.
    """
    message = query.message
    if message is not None and message.photo:
        await _send_text_message(
            query,
            context,
            text,
            reply_markup=reply_markup,
            parse_mode=parse_mode,
        )
        return
    try:
        await query.edit_message_text(
            text=text,
            parse_mode=parse_mode,
            reply_markup=reply_markup,
        )
        return
    except BadRequest:
        logger.debug("present_message: edit ignorado", exc_info=True)
    await _send_text_message(
        query,
        context,
        text,
        reply_markup=reply_markup,
        parse_mode=parse_mode,
    )


async def restore_menu_after_error(
    query: CallbackQuery,
    context: CustomContext,
    text: str,
    *,
    parse_mode: str | None = ParseMode.MARKDOWN,
) -> None:
    """Devolve um teclado de menu quando o loading já tirou os botões."""
    await present_message(
        query,
        context,
        text,
        reply_markup=keyboards.main_menu_keyboard(),
        parse_mode=parse_mode,
    )


async def route_menu_callback(update: Update, context: CustomContext) -> None:
    """Encaminha um callback de menu para o handler do destino.

    Não responde o callback aqui: cada destino chama ``query.answer()``.
    """
    query = update.callback_query
    data = query.data if query is not None else ""
    if data in {"menu_home", "mal_m", "wl_m"}:
        await show_main_menu(update, context)
        return
    if data == "menu_meus_alertas":
        from handlers.meus_alertas import meus_alertas_callback

        await meus_alertas_callback(update, context)
        return
    if data == "menu_watchlist":
        from handlers.watchlist import watchlist_menu_callback

        await watchlist_menu_callback(update, context)
        return
    if data == "menu_ajuda":
        from handlers.setup import main_menu_callback

        await main_menu_callback(update, context)


async def _present_main_menu(query: CallbackQuery, context: CustomContext) -> None:
    await present_message(
        query,
        context,
        menus.menu_principal_inline(),
        reply_markup=keyboards.main_menu_keyboard(),
    )


async def _send_text_message(
    query: CallbackQuery,
    context: CustomContext,
    text: str,
    *,
    reply_markup: InlineKeyboardMarkup | None,
    parse_mode: str | None,
) -> None:
    chat_id = _chat_id(query, context)
    if chat_id is None:
        return
    await context.bot.send_message(
        chat_id=chat_id,
        text=text,
        parse_mode=parse_mode,
        reply_markup=reply_markup,
    )


def _chat_id(query: CallbackQuery, context: CustomContext) -> int | None:
    del context
    if query.message is not None:
        return query.message.chat_id
    user = query.from_user
    return user.id if user is not None else None
