# Imóvel Radar Setup

## Prerequisites

- Python >= 3.13
- [uv](https://docs.astral.sh/uv/) (Python package manager)
- Node.js >= 18
- pnpm >= 10 (Node.js package manager)

## Initial setup (once)

```bash
pnpm run setup
```

This runs:

1. `setup:shared-models` — syncs `shared-models` package dependencies
2. `setup:scraper` — creates `.venv` in scraper, installs `shared-models` as editable, syncs deps
3. `setup:bot` — same for bot
4. `pnpm install` — installs Node.js dependencies (frontend, Turborepo, etc.)

## Environment variables

```bash
cp apps/scraper/.env.example apps/scraper/.env
# edit apps/scraper/.env if needed

cp apps/bot/.env.example apps/bot/.env
# edit apps/bot/.env with TELEGRAM_BOT_TOKEN and SCRAPER_API_URL
```

## Running the services

### All at once

```bash
pnpm run dev
```

### Individually

```bash
pnpm run dev:scraper   # FastAPI on port 8000
pnpm run dev:bot       # Telegram Bot (port 3333)
pnpm run dev:frontend  # Next.js (optional)
```

## Lint and type checking

The project uses two tools run via terminal (VS Code Pylance is disabled):

### Ruff (lint)

Checks code style, unused imports, formatting.

```bash
cd apps/scraper && uv run ruff check .
cd apps/bot    && uv run ruff check .
```

To auto-fix:

```bash
cd apps/scraper && uv run ruff check . --fix
cd apps/bot    && uv run ruff check . --fix
```

### Pyright (type checking)

Checks type consistency, attribute access, function calls.

```bash
cd apps/scraper && uv run pyright
cd apps/bot    && uv run pyright
```

### Run both at once

```bash
cd apps/scraper && uv run ruff check . && uv run pyright
cd apps/bot    && uv run ruff check . && uv run pyright
```

## `shared-models` structure

```
packages/shared-models/
├── pyproject.toml                ← build-system + metadata
├── uv.lock                       ← dependency lockfile
└── src/
    └── shared_models/            ← Python package (import shared_models)
        ├── __init__.py           ← re-exports everything
        ├── api_schemas.py        ← REST route schemas
        ├── models.py             ← domain models (Listing, Alert, etc.)
        └── utils.py              ← utilities (format_brl, money_to_int)
```

Each app installs `shared-models` as **editable** (declared in `pyproject.toml` via `[tool.uv.sources]`). Run `pnpm run setup` to install it automatically.

This creates a symlink to the source code — any change in `shared-models` reflects immediately.

## VS Code

The `.vscode/settings.json` file at the root disables Pylance (VS Code language server) because real validation is done via `ruff` + `pyright` in the terminal.

To re-enable Pylance, remove or edit `.vscode/settings.json`. Make sure to select the correct `.venv` interpreter:

- For scraper files: `apps/scraper/.venv/Scripts/python.exe`
- For bot files: `apps/bot/.venv/Scripts/python.exe`