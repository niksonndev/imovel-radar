# Imóvel Radar — Monorepo

Monorepo managed with Turborepo. Current structure:

```
imovel-radar/
├── apps/
│   └── backend/      # Python — Telegram bot + OLX scraper + scheduler
├── assets/            # shared (images, demo gifs etc)
└── README.md
```

`apps/frontend/` does not exist yet — do not assume it exists until it's created.

## Documentation reference (Context MCP)

Turborepo docs are indexed locally via the Context MCP tool as `turborepo@2.10.6` (source: `apps/docs` from `vercel/turborepo`, not the root `/docs` folder). Use this instead of relying on training data or guessing CLI flags/config for `turbo.json`.

## General conventions

- Commits follow Conventional Commits (`feat:`, `fix:`, `chore:`, `refactor:`, `docs:`).
- Never commit `.env` — only `.env.example` should go into git.
- When moving/renaming files, use `git mv` to preserve history.
- Each app inside `apps/` should be self-contained: dependencies, config, and virtual env/venv live inside the app itself, not at the monorepo root.

## When unsure

If a task seems to touch more than one app (e.g. an API contract between backend and a future frontend), stop and ask before generalizing — don't assume conventions from the other side without confirmation.