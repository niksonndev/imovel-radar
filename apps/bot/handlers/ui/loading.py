"""Loading explícito em callbacks que batem no Postgres (wake do Neon)."""

from __future__ import annotations

import logging
import re

from telegram import CallbackQuery
from telegram.constants import ParseMode
from telegram.error import BadRequest

from handlers.ui import menus

logger = logging.getLogger(__name__)

# Callbacks cujo handler (ou o ensure_user) abre sessão no Postgres.
# Exclui mal_m / wl_m (só voltam ao menu) e navegação de carrossel.
_DB_LOADING_CALLBACK_RE = re.compile(
    r"^(?:"
    r"menu_meus_alertas|menu_watchlist|"
    r"mal_(?:b$|p_|ed_|rm_)|"
    r"wl_(?:b$|p_|rm_|confirm_yes$)|"
    r"email_pro_trial$|"
    r"pro_subscribe$"
    r")"
)


def callback_needs_db_loading(callback_data: str | None) -> bool:
    if not callback_data:
        return False
    return _DB_LOADING_CALLBACK_RE.match(callback_data) is not None


async def show_db_loading(query: CallbackQuery) -> None:
    """Troca a mensagem por um loading com ⏳ *sem* responder o callback.

    Assim o spinner do botão continua até o handler chamar ``answer()``, e o
    toast de ações (ex.: \"Alerta removido.\") ainda funciona. Em mensagens de
    foto (carrossel) o edit falha — ignoramos.
    """
    try:
        await query.edit_message_text(
            text=menus.db_loading(),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=None,
        )
    except BadRequest as exc:
        logger.debug("show_db_loading: edit ignorado (%s)", exc)
