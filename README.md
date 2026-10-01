# André Assistente Imobiliário

Assistente imobiliário que ajuda a encontrar imóveis em anúncios públicos do OLX. O André conversa pelo WhatsApp e acompanha buscas de aluguel e venda nas cidades cobertas.

**Atendimento:** [fale com André pelo WhatsApp](https://wa.me/5582993345293). Pagamentos não estão disponíveis no momento.

As CTAs do site abrem o WhatsApp. `/novidades` concentra comunicados oficiais.

## Stack

- **Monorepo**: Turborepo + pnpm (Node.js workspaces for the frontend)
- **Scraper** (Lambda + FastAPI local): coleta OLX → `listing` no Postgres (Neon)
- **André no WhatsApp** (`apps/whatsapp-bot`, Rust, processo sempre ligado): assistente imobiliário, deploy Render com disco para a sessão
- **Telegram legado** (`apps/bot`): mantido temporariamente para comunicar o encerramento e limpar dados; não é o canal principal do produto
- **Shared package**: `shared-models` — table models SQLModel + utils; `api_schemas` está deprecated
- **Database**: Postgres via SQLModel + Alembic (dev: local; prod: Neon pooled)
- **Estado de conversa (prod)**: DynamoDB

## Structure

```text
imovel-radar/
├── packages/
│   └── shared-models/        ← tables SQLModel + domain models + utils
│       └── src/
│           ├── tables.py
│           ├── models.py
│           ├── api_schemas.py  (deprecated)
│           └── utils.py
├── apps/
│   ├── scraper/              ← dono de `listing`; coleta OLX (Lambda em prod)
│   ├── bot/                  ← legado temporário para o aviso de encerramento Telegram
│   ├── whatsapp-bot/         ← André Assistente Imobiliário (Rust, Render, disco /data)
│   └── frontend/             ← Next.js 16 (App Router, SSG → out/)
├── docs/
│   └── adr/
│       └── separate-scraper-from-bot.md
├── assets/
├── turbo.json
├── pnpm-workspace.yaml
└── package.json
```

## Architecture / Flow

```text
    EventBridge (coleta diária)
      │
      ▼
    Scraper Lambda ──────► Neon Postgres
               ▲
               │
          André Assistente
          WhatsApp / Render
```

  O scraper coleta anúncios e o assistente WhatsApp lê as listagens e atende os usuários pelo canal oficial.

### Daily scrape flow

```text
EventBridge → scraper Lambda → job_daily()
  → search_all_rent_maceio()
  → extract_listings_from_search_page()
  → upsert listing
```

### Notification flow (WhatsApp)

```text
run_daily_notifications()
  → notify_new_matches()
      → SELECT users / unnotified listings por alerta
      → send_carousel() / INSERT alert_matches
  → notify_watched_changes()
      → diffs em watched_listings vs listing
      → mensagem de preço/status / update baselines
```

### Alert flow

```text
Pessoa → descreve o imóvel que procura
  → André interpreta bairro, preço e tipo de imóvel
  → cria alerta e envia opções compatíveis pelo WhatsApp
```

## Privacy

Para solicitar a exclusão dos dados, envie `excluir dados` pelo WhatsApp e confirme a solicitação.

## Running

### Setup (once)

```bash
pnpm run setup
```

Configure os arquivos `.env` dos serviços que for executar:

- `apps/scraper/.env` — copy from `apps/scraper/.env.example`
- `apps/bot/.env` — necessário somente para o aviso final Telegram durante a desativação

### Run everything

```bash
pnpm run dev
```

### Run a single service

```bash
pnpm run dev:scraper   # FastAPI on port 8000
pnpm run dev:whatsapp  # André no WhatsApp (Rust; pareie o QR em /pair)
pnpm run dev:frontend  # Next.js (optional)
```

## Lint and type checking

The project uses **Ruff** for linting and **Pyright** for type checking via the terminal.
VS Code Pylance is disabled; the actual validation is done through the commands below.

```bash
# Scraper
cd apps/scraper && uv run ruff check . && uv run pyright

# Bot
cd apps/bot && uv run ruff check . && uv run pyright
```

## Tests

Run the full test suite from the repository root:

```bash
pnpm run test
```

To run only the scraper tests:

```bash
pnpm run test --filter scraper
```

## CI: Scraper tests

The repository includes a GitHub Actions workflow in [.github/workflows/scraper-tests.yml](.github/workflows/scraper-tests.yml) that runs the scraper test suite automatically on pushes to `main` and on pull requests that touch [apps/scraper](apps/scraper) or the workflow file itself.

It installs dependencies with `uv`, sets up Python, and executes:

```bash
cd apps/scraper && uv run pytest -v
```

See [`docs/setup.md`](docs/setup.md) for details.
