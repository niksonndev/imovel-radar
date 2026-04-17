"""
Pacote do bot Telegram: handlers, conversas e UI.

- ``setup`` (em ``bot.setup``): registra comandos e o ``ConversationHandler``.
- ``create_new_alert`` / ``carousel``: fluxos que falam com o usuário e com o SQLite.
- ``bot.ui``: textos e teclados reutilizáveis (sem lógica de negócio pesada).

O scraper não é importado aqui; ``main.py`` monta o ``Application`` e chama ``setup``.
"""
