# André Assistente Imobiliário — setup local

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
3. `setup:bot` — same for the legacy Telegram runtime, retained only for shutdown communication
4. `pnpm install` — installs Node.js dependencies (frontend, Turborepo, etc.)

## Environment variables

```bash
cp apps/scraper/.env.example apps/scraper/.env
# edit apps/scraper/.env if needed

cp apps/whatsapp-bot/.env.example apps/whatsapp-bot/.env
# edit apps/whatsapp-bot/.env with DATABASE_URL and WhatsApp settings

# Legacy Telegram shutdown notice only; configure DATABASE_URL and AWS access for its token
cp apps/bot/.env.example apps/bot/.env
```

## Running the services

### All at once

```bash
pnpm run dev
```

### Individually

```bash
pnpm run dev:scraper   # FastAPI on port 8000
pnpm run dev:whatsapp  # André Assistente Imobiliário
pnpm run dev:frontend  # Next.js (optional)
```

The Telegram runtime is excluded from the default local workflow. To preview
the final notice without sending it, run from `apps/bot`:

```bash
uv run --project . --group dev python send_final_notice.py
```

The production send requires AWS/database access and an explicit recipient
count confirmation; do not use a local database for the announcement.

## Lint and type checking

The project uses two tools run via terminal (VS Code Pylance is disabled):

### Ruff (lint)

Checks code style, unused imports, formatting.

```bash
cd apps/scraper && uv run ruff check .
```

To auto-fix:

```bash
cd apps/scraper && uv run ruff check . --fix
```

### Pyright (type checking)

Checks type consistency, attribute access, function calls.

```bash
cd apps/scraper && uv run pyright
```

### Run both at once

```bash
cd apps/scraper && uv run ruff check . && uv run pyright
```

## `shared-models` structure

```
packages/shared-models/
├── pyproject.toml                ← build-system + metadata
├── uv.lock                       ← dependency lockfile
└── src/
    └── shared_models/            ← Python package (import shared_models)
        ├── __init__.py           ← re-exports everything
        ├── tables.py            ← SQLModel table models (schema físico)
        ├── models.py            ← domain models (Listing, Alert, etc.)
        ├── api_schemas.py       ← deprecated (antiga API REST)
        └── utils.py             ← utilities (format_brl, money_to_int)
```

Each app installs `shared-models` as **editable** (declared in `pyproject.toml` via `[tool.uv.sources]`). Run `pnpm run setup` to install it automatically.

This creates a symlink to the source code — any change in `shared-models` reflects immediately.

## VS Code

The `.vscode/settings.json` file at the root disables Pylance (VS Code language server) because real validation is done via `ruff` + `pyright` in the terminal.

To re-enable Pylance, remove or edit `.vscode/settings.json`. Make sure to select the correct `.venv` interpreter:

- For scraper files: `apps/scraper/.venv/Scripts/python.exe`
- For the legacy notice utility: `apps/bot/.venv/bin/python`