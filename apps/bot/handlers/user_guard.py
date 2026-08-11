from __future__ import annotations

import logging

from telegram import Update
from telegram.constants import ChatType

from handlers.api_client import create_user, get_user
from models import CustomContext

logger = logging.getLogger(__name__)

# Cache simples de chat_ids já verificados/criados
_known_chat_ids: set[int] = set()


async def ensure_user(chat_id: int) -> bool:
    """Garante que o usuário existe no scraper; cria se necessário.

    Retorna ``True`` se o usuário estiver disponível (ou acabou de ser criado)
    e ``False`` se a garantia falhar.
    """
    if chat_id in _known_chat_ids:
        return True

    try:
        await get_user(chat_id)
    except Exception:
        try:
            await create_user(chat_id)
        except Exception:
            logger.exception("Falha ao garantir/criar usuário %s", chat_id)
            return False

    _known_chat_ids.add(chat_id)
    return True


async def ensure_user_callback(update: Update, context: CustomContext) -> bool | None:
    """Callback genérico: garante usuário sem consumir o update."""
    query = update.callback_query
    if query is None:
        return None
    user = update.effective_user
    if user is None:
        return None
    await query.answer()
    if not await ensure_user(user.id):
        await query.edit_message_text(
            "⚠️ Não foi possível verificar seu usuário no momento. "
            "Tente novamente em instantes.",
            reply_markup=None,
        )
        return True  # consome; handlers específicos não seguem
    return None  # não consome; handlers específicos seguem


async def ensure_user_message(update: Update, context: CustomContext) -> bool | None:
    """Mensagem genérica: garante usuário sem consumir o update."""
    user = update.effective_user
    if user is None:
        return None
    if not await ensure_user(user.id):
        message = update.effective_message
        chat = update.effective_chat
        if (
            message is not None
            and chat is not None
            and chat.type == ChatType.PRIVATE
        ):
            await message.reply_text(
                "⚠️ Não foi possível verificar seu usuário no momento. "
                "Tente novamente em instantes.",
            )
        return True  # consome; handlers específicos não seguem
    return None  # não consome; handlers específicos seguem
