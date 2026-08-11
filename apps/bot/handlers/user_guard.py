from __future__ import annotations

import logging

from telegram import Update

from handlers.api_client import create_user, get_user
from models import CustomContext

logger = logging.getLogger(__name__)

# Cache simples de chat_ids já verificados/criados
_known_chat_ids: set[int] = set()


async def ensure_user(chat_id: int) -> None:
    """Garante que o usuário existe no scraper; cria se necessário."""
    if chat_id in _known_chat_ids:
        return

    try:
        await get_user(chat_id)
    except Exception:
        try:
            await create_user(chat_id)
        except Exception:
            logger.exception("Falha ao garantir/criar usuário %s", chat_id)
            return

    _known_chat_ids.add(chat_id)


async def ensure_user_callback(update: Update, context: CustomContext) -> bool | None:
    """Callback genérico: garante usuário sem consumir o update."""
    query = update.callback_query
    if query is None:
        return None
    user = update.effective_user
    if user is None:
        return None
    await ensure_user(user.id)
    return None  # não consome; handlers específicos seguem


async def ensure_user_message(update: Update, context: CustomContext) -> bool | None:
    """Mensagem genérica: garante usuário sem consumir o update."""
    user = update.effective_user
    if user is None:
        return None
    await ensure_user(user.id)
    return None  # não consome; handlers específicos seguem
