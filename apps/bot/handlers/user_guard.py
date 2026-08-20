import logging

import handlers.api_client as data

logger = logging.getLogger(__name__)

# Cache simples de chat_ids já verificados/criados (por instância quente)
_known_chat_ids: set[int] = set()


async def ensure_user(chat_id: int) -> bool:
    """Garante que o usuário existe no banco; cria se necessário.

    Retorna ``True`` se o usuário estiver disponível (ou acabou de ser criado)
    e ``False`` se a garantia falhar.
    """
    if chat_id in _known_chat_ids:
        return True

    if await data.ensure_user(chat_id):
        _known_chat_ids.add(chat_id)
        return True
    return False

