from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import Application

from handlers.user_guard import ensure_user

logger = logging.getLogger(__name__)


class RadarApplication(Application):
    """``Application`` que garante a existência do usuário no scraper em cada update.

    A garantia roda **antes** de qualquer handler (comandos, callbacks, mensagens
    e passos de conversa) cobrindo todos os updates, sem "consumir" o update —
    ou seja, sem impedir que os handlers específicos sejam chamados. Em vez de
    depender de um ``MessageHandler`` global (que no PTB interrompe o grupo após
    o primeiro match), sobrepomos :meth:`process_update`.

    Falhas de garantia são apenas logadas aqui; a resposta de erro amigável fica
    a cargo dos handlers específicos, caso queiram.
    """

    async def process_update(self, update: object) -> None:
        if isinstance(update, Update):
            user = update.effective_user
            if user is not None and not await ensure_user(user.id):
                logger.warning("Não foi possível garantir usuário %s no scraper", user.id)

        await super().process_update(update)
