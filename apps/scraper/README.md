# Scraper — Imóvel Radar

Serviço FastAPI responsável por toda a lógica de negócio do Imóvel Radar:

- **Proprietário exclusivo do banco SQLite** (`data/imoveis.db`)
- Realiza scraping diário do OLX (aluguel em Maceió)
- Expõe API REST para consulta de listings, alertas e matches
- Scheduler interno (APScheduler) roda o scrape diário no mesmo processo

## Endpoints

### Health

| Método | Rota | Descrição |
|--------|------|-----------|
| GET | `/health` | Status + contagens do banco |

### Listings

| Método | Rota | Descrição |
|--------|------|-----------|
| GET | `/listings` | Lista listings (filtro opcional: `?ids=1,2,3` ou `?since=timestamp`) |
| GET | `/listings/{list_id}` | Listing por ID |
| GET | `/listings/neighbourhoods` | Bairros de Maceió |

### Alerts

| Método | Rota | Descrição |
|--------|------|-----------|
| POST | `/alerts` | Criar alerta (body: `CreateAlertRequest`) |
| GET | `/alerts` | Listar alertas (`?user_id=chat_id`) |
| GET | `/alerts/{id}` | Detalhe do alerta |
| DELETE | `/alerts/{id}` | Remover alerta (`?user_id=chat_id`) |
| GET | `/alerts/{id}/matches` | Matches não notificados |
| POST | `/alerts/{id}/matches/notify` | Marcar matches como notificados |
| GET | `/alerts/active` | Todos alertas ativos (para polling) |

## Configuração

Variáveis de ambiente (`.env`):

```
LOG_LEVEL=INFO
API_PORT=8000
SCRAPE_CRON_HOUR=8
SCRAPE_CRON_MINUTE=0
SCRAPE_TIMEZONE=America/Maceio
MACEIO_RENT_LISTINGS_URL=https://www.olx.com.br/imoveis/aluguel/estado-al/alagoas/maceio
```

## Como rodar

```bash
cd apps/scraper
uv pip install -e ../../packages/shared-models
uv sync
uv run uvicorn main:app --reload --port 8000
```

## Arquitetura

```
apps/scraper/
├── main.py              # FastAPI app + lifespan (cria tabelas, inicia scheduler)
├── config.py            # Variáveis de ambiente (OLX, scrape, delay)
├── database/            # SQLite (schema, queries, db, users)
├── scraper/             # OLX scraper + parser (RSC payload extraction)
├── api/                 # Rotas FastAPI (health, listings, alerts)
├── scheduler/           # APScheduler (job_daily: scrape + upsert)
└── data/                # SQLite database directory