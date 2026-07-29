"""
Pacote do bot Telegram: handlers, conversas e UI.

- ``setup`` (em ``bot.setup``): registra comandos e o ``ConversationHandler``.
- ``create_new_alert`` / ``carousel`` / ``meus_alertas``: fluxos que
falam com o usuário e com o scraper via API.
"""

from . import setup  # noqa: F401
