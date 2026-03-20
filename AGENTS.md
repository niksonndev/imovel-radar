# Regras do projeto (Cursor)

## Contexto
Projeto: **Imovel Radar** (bot Telegram em Python) que monitora anúncios do **OLX** para **Maceió/AL**.
Ele **não** é um servidor web: fica rodando em *long polling* via `py main.py`.

## Regras para o AI no Cursor
- Responder **sempre em Português**.
- Ao mexer em código, explique rapidamente **o que vai mudar e por quê** antes de sugerir/alterar.
- Preferir mudanças mínimas e consistentes com o estilo do repositório (mantendo o fluxo: `main.py` → `bot/*` → `scraper/*` → `database/*` → `scheduler/*`).
- Considerar a suíte de testes ao propor mudanças em lógica (especialmente `database/*` e `scraper/*`).

## Testes (pytest)
O repositório tem testes em `tests/` (CRUD, parser, montagem de URL e filtros locais).
- Rodar: `pytest -q`
- Observação: testes **não** dependem de scraping real do OLX; eles validam parsing/transformações e lógica de banco.

## Rodar o bot
- Primeiro: configurar `.env` com `TELEGRAM_BOT_TOKEN`.
- Em seguida: `py main.py`
- O SQLite é criado automaticamente em `data/bot.db` na primeira execução.
