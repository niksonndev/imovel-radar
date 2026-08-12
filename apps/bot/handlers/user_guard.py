import logging

from handlers.api_client import create_user, get_user

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
