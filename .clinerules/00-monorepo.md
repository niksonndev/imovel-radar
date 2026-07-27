# Imóvel Radar — Monorepo

Monorepo managed with Turborepo (pnpm workspace). Current structure:

```
imovel-radar/
├── apps/
│   ├── backend/          # Python — Telegram bot + OLX scraper + scheduler
│   │   └── package.json  # wrapper scripts (dev → python main.py)
│   └── frontend/         # Next.js (App Router) + Tailwind + shadcn/ui + Bold theme
│       ├── src/
│       ├── DEPLOY.md     # manual Vercel deploy steps
│       └── package.json
├── assets/               # shared (images, demo gifs etc)
├── turbo.json            # pipeline: build, dev (persistent), lint
├── pnpm-workspace.yaml   # points to apps/*
├── package.json          # root scripts → turbo run
├── .gitignore
└── README.md
```

## Documentation reference (Context MCP)

Turborepo docs are indexed locally via the Context MCP tool as `turborepo@2.10.6`. Use this instead of relying on training data or guessing CLI flags/config for `turbo.json`.

## General conventions

- Commits follow Conventional Commits (`feat:`, `fix:`, `chore:`, `refactor:`, `docs:`).
- Never commit `.env` — only `.env.example` should go into git.
- When moving/renaming files, use `git mv` to preserve history.
- Each app inside `apps/` should be self-contained: dependencies, config, and virtual env/venv live inside the app itself, not at the monorepo root.
- Frontend uses **tailwindcss v4** with custom CSS variables. The theme tokens are defined in `globals.css` (Bold design system: primary=#0077BC, secondary=#009866).
- Fonts: Archivo Black (headings/body), JetBrains Mono (mono/caps) — loaded via Next.js `next/font/google` in `layout.tsx`.
- Backend wrapper `package.json` scripts delegate to Python tools — no Node.js runtime needed for the backend.

## Commands

```bash
pnpm run dev     # turbo run dev — starts all apps in dev mode
pnpm run build   # turbo run build — builds all apps
pnpm run lint    # turbo run lint — lints all apps
```

## When unsure

If a task seems to touch more than one app (e.g. an API contract between backend and a future frontend), stop and ask before generalizing — don't assume conventions from the other side without confirmation.
