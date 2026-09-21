"""
Pacote do bot Telegram: handlers, conversas e UI.

- ``setup``: registra comandos e o ``ConversationHandler``.
- ``create_new_alert`` / ``carousel`` / ``meus_alertas``: fluxos que
  falam com o usuário e leem/escrevem o Postgres compartilhado (ADR 0005).
"""

from . import setup  # noqa: F401
