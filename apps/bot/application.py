from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import Application, BasePersistence, ContextTypes

import config
from handlers.setup import setup
from handlers.user_guard import ensure_user

logger = logging.getLogger(__name__)


class RadarApplication(Application):
    """``Application`` que garante a existência do usuário no banco em cada update.

    A garantia roda **antes** de qualquer handler (comandos, callbacks, mensagens
    e passos de conversa) cobrindo todos os updates, sem "consumir" o update —
    ou seja, sem impedir que os handlers específicos sejam chamados. Em vez de
    depender de um ``MessageHandler`` global, sobrepomos :meth:`process_update`.

    Falhas de garantia são apenas logadas aqui; a resposta de erro amigável fica
    a cargo dos handlers específicos, caso queiram.
    """

    async def process_update(self, update: object) -> None:
        if isinstance(update, Update):
            user = update.effective_user
            if user is not None and not await ensure_user(user.id):
                logger.warning("Não foi possível garantir usuário %s no banco", user.id)

        await super().process_update(update)


def build_application(
    persistence: BasePersistence,
    context_types: ContextTypes,
) -> Application:
    """Constrói a Application do bot (reuso do lambda_handler / dev)."""
    app = (
        Application.builder()
        .application_class(RadarApplication)
        .token(config.get_bot_token())
        .context_types(context_types)
        .persistence(persistence)
        .build()
    )
    setup(app)
    return app

