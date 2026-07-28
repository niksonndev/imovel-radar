# imovel-radar 🏠

Bot Telegram + Scraper para monitorar anúncios de imóveis no OLX Maceió. O scraper coleta anúncios diariamente, e o bot notifica usuários quando novos imóveis correspondem aos seus alertas cadastrados.

![Demonstração: `/start`, menu principal e início do fluxo Novo Alerta](assets/demo-aluguel.gif)

## Stack

- **Monorepo**: Turborepo + pnpm (workspaces Node.js para o frontend)
- **Scraper** (FastAPI, porta 8000): `cloudscraper` + `BeautifulSoup4` + `APScheduler`
- **Bot** (python-telegram-bot, porta 3333): `httpx` (cliente HTTP para o scraper)
- **Pacote compartilhado**: `shared-models` — schemas Pydantic do contrato entre serviços
- **Banco**: SQLite via `sqlite3` nativo (exclusivo do scraper)

## Estrutura

```
imovel-radar/
├── packages/
│   └── shared-models/        ← Schemas Pydantic do contrato (Listing, Alert, etc.)
│       └── src/
│           ├── models.py
│           ├── api_schemas.py
│           └── utils.py
├── apps/
│   ├── scraper/              ← FastAPI — dono do SQLite, scrape OLX, expõe API REST
│   │   ├── main.py           (FastAPI + lifespan → APScheduler)
│   │   ├── config.py         (OLX URLs, delay, user-agents)
│   │   ├── database/         (schema, queries, db, users)
│   │   ├── scraper/          (olx_scraper, parser)
│   │   ├── api/               (health, listings, alerts)
│   │   ├── scheduler/        (APScheduler — scrape diário)
│   │   ├── data/              (imoveis.db)
│   │   ├── docs/
│   │   │   ├── README.md
│   │   │   ├── olx-scraper.md
│   │   │   └── parser.md
│   │   └── README.md
│   ├── bot/                  ← PTB — cliente "dumb" da API do scraper
│   │   ├── main.py           (Application PTB + polling setup)
│   │   ├── config.py         (TELEGRAM_BOT_TOKEN, SCRAPER_API_URL)
│   │   ├── models.py         (CustomContext, UserData, wizard types)
│   │   ├── handlers/         (conversação, UI, api_client)
│   │   │   ├── api_client.py (httpx → scraper)
│   │   │   ├── carousel.py
│   │   │   ├── create_new_alert.py
│   │   │   ├── meus_alertas.py
│   │   │   ├── hydrator.py
│   │   │   ├── setup.py
│   │   │   └── ui/           (keyboards, menus)
│   │   ├── jobs/              (polling_job — matches a cada 1h)
│   │   └── README.md
│   └── frontend/             ← Next.js (unchanged)
├── docs/
│   └── adr/
│       └── separate-scraper-from-bot.md
├── assets/
├── turbo.json
├── pnpm-workspace.yaml
└── package.json
```

## Arquitetura / Fluxo

```
                    ┌───────────────────┐
                    │  Scraper (8000)   │
                    │  FastAPI          │
                    │                   │
  ┌─────────┐  cron │  ┌─────────────┐  │
  │ APSched.│──────▶│  │ scrape OLX  │  │
  │ diário  │       │  │ → upsert DB │  │
  └─────────┘       │  └─────────────┘  │
                    │                   │
                    │  ┌─────────────┐  │
                    │  │ API REST    │  │
                    │  │ /listings   │  │
                    │  │ /alerts     │  │
                    │  │ /matches    │  │
                    │  └─────────────┘  │
                    └────────┬──────────┘
                             │ HTTP (localhost)
                    ┌────────▼──────────┐
                    │  Bot (3333)       │
                    │  python-telegram- │
                    │  bot + httpx      │
                    │                   │
  ┌─────────┐       │  ┌─────────────┐  │
  │ Polling │       │  │ Handlers    │  │
  │ 1 hora  │──────▶│  │ → Telegram  │  │
  └─────────┘       │  └─────────────┘  │
                    └───────────────────┘
```

### Fluxo do scrape diário

```
APScheduler → job_daily()
  → search_all_rent_maceio()          # cloudscraper: todas as páginas da OLX
  → extract_listings_from_search_page()  # parser RSC: descarta sem foto
  → upsert listings no banco          # INSERT OR REPLACE em listings
```

### Fluxo de notificação (polling no bot, a cada 1h)

```
JobQueue do PTB → notify_new_matches()
  → GET /alerts/active/with-chat            # todos alertas ativos + chat_id
  → para cada alerta:
      GET /alerts/{id}/matches               # matches não notificados
      send_carousel()                        # envia carrossel ao usuário
      POST /alerts/{id}/matches/notify       # marca como notificados
```

### Fluxo do wizard `/novo_alerta`

```
Usuário → escolhe preço → seleciona bairros → nome → confirma
  → POST /alerts                  # cria alerta no scraper
  → GET /alerts/{id}/matches      # busca matches atuais
  → send_carousel()               # envia resultados
  → POST /alerts/{id}/matches/notify  # marca como notificados
```

## Comandos do bot

| Comando | Descrição | Status |
|---|---|---|
| `/start` | Boas-vindas e menu principal | ✅ |
| `/novo_alerta` | Wizard para cadastrar alerta | ✅ |
| `/ajuda` | Lista de comandos | ✅ |

## Como rodar

### Setup (uma vez)

```bash
pnpm run setup
```

Em seguida, configure os arquivos `.env`:

- `apps/scraper/.env` — copie de `apps/scraper/.env.example`
- `apps/bot/.env` — configure `TELEGRAM_BOT_TOKEN` e `SCRAPER_API_URL=http://localhost:8000`

### Rodar tudo

```bash
pnpm run dev
```

### Rodar apenas um serviço

```bash
pnpm run dev:scraper   # FastAPI na porta 8000
pnpm run dev:bot       # Bot Telegram
pnpm run dev:frontend  # Next.js (opcional)