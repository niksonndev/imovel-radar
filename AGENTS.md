# AGENTS.md

## Cursor Cloud specific instructions

### Overview

This is **Imovel Radar**, a single-process Python Telegram bot that monitors real estate listings on OLX (Maceió/AL, Brazil). It is NOT a web server — it runs as a long-polling process talking to the Telegram API.

### Prerequisites

- Python 3.11+ (the VM has 3.12)
- A valid `TELEGRAM_BOT_TOKEN` from [@BotFather](https://t.me/BotFather) — set it in `.env` or as an environment variable. Without it, `config.py` raises `RuntimeError` on import and `main.py` cannot start.
- `python3.12-venv` apt package is required to create the virtualenv (not installed by default on the VM).

### Running the bot

```bash
source /workspace/.venv/bin/activate
python main.py
```

The bot runs indefinitely via long-polling. Stop with Ctrl+C.

### Key caveats

- **No tests or linter**: the repository has no test suite and no linting configuration (no `pytest`, `ruff`, `flake8`, `mypy`, etc.). There is nothing to run for lint/test checks.
- **No build step**: the bot is run directly via `python main.py`.
- **SQLite auto-created**: the database file `data/bot.db` is created automatically on first run — no migrations needed.
- **`.env` file**: copy from `.env.example` and set `TELEGRAM_BOT_TOKEN`. Other variables have sensible defaults (see `README.md` for the full list).
- **The `PTBUserWarning` about `per_message=False`** in `bot/conversations.py:222` is expected and harmless.
