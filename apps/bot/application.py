from __future__ import annotations

import logging
from collections.abc import Callable, Coroutine
from typing import Any

from telegram import Update
from telegram.ext import Application, BasePersistence, ContextTypes

import config
from handlers.setup import setup
from handlers.ui.loading import callback_needs_db_loading, show_db_loading
from handlers.user_guard import ensure_user

logger = logging.getLogger(__name__)

_PostInit = Callable[[Application], Coroutine[Any, Any, None]]


class RadarApplication(Application):
    """``Application`` que garante a existência do usuário no banco em cada update.

    A garantia roda **antes** de qualquer handler (comandos, callbacks, mensagens
    e passos de conversa) cobrindo todos os updates, sem "consumir" o update —
    ou seja, sem impedir que os handlers específicos sejam chamados. Em vez de
    depender de um ``MessageHandler`` global, sobrepomos :meth:`process_update`.

    Em callbacks que batem no Postgres, mostra um loading com ⏳ *antes* do
    ``ensure_user``, para o wake do Neon (free tier) ficar visível na mensagem
    — não só no latejar do botão.

    Falhas de garantia são apenas logadas aqui; a resposta de erro amigável fica
    a cargo dos handlers específicos, caso queiram.
    """

    async def process_update(self, update: object) -> None:
        if isinstance(update, Update):
            query = update.callback_query
            if query is not None and callback_needs_db_loading(query.data):
                await show_db_loading(query)

            user = update.effective_user
            if user is not None and not await ensure_user(user.id):
                logger.warning("Não foi possível garantir usuário %s no banco", user.id)

        await super().process_update(update)


def build_application(
    persistence: BasePersistence,
    context_types: ContextTypes,
    post_init: _PostInit | None = None,
    post_shutdown: _PostInit | None = None,
) -> Application:
    """Constrói a Application do bot (reuso do lambda_handler / dev)."""
    builder = (
        Application.builder()
        .application_class(RadarApplication)
        .token(config.get_bot_token())
        .context_types(context_types)
        .persistence(persistence)
    )
    if post_init is not None:
        builder = builder.post_init(post_init)
    if post_shutdown is not None:
        builder = builder.post_shutdown(post_shutdown)
    app = builder.build()
    setup(app)
    return app

