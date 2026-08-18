# Lambda / EventBridge — Coleta diária

A coleta do OLX deixou de rodar por um scheduler em processo (APScheduler) e
passou a ser executada como uma **AWS Lambda invocada por EventBridge**
(ADRs 0004/0005). O scraper continua dono do write de `listing`; a Lambda só
coleta e persiste — notificações são responsabilidade do bot.

## Entry point

`lambda_handler.py`:

- `lambda_handler(event, context)` — handler síncrono do Lambda (trigger
  EventBridge); executa `asyncio.run(job_daily())` e retorna
  `{"success": 0|1, "count": N}`.
- Em exceção inesperada, loga e retorna `{"success": 0, "count": 0}`
  (formato amigável para alarme CloudWatch).
- **Nunca roda migrations** (Alembic é step do pipeline, não do runtime) e
  **não importa o app FastAPI** (sem uvicorn na imagem).

## Fluxo

```text
EventBridge (cron)
  → lambda_handler()
    → job_daily()                    # scheduler/jobs.py
      → search_all_rent_maceio()     # collector (OLX, delay 2–4s)
      → upsert_listing()             # Postgres, por listing_id (idempotente)
  → {"success", "count"}
```

O upsert por `listing_id` é idempotente: re-execuções (retry, invocação
manual) são seguras. `search_all_rent_maceio()` para no primeiro erro e
persiste o que já foi coletado (coleta parcial é aceitável).

## Configuração

```bash
DATABASE_URL=postgresql+psycopg://...
LOG_LEVEL=INFO
SCRAPER_MAX_PAGES=100        # limite de páginas (default hardcoded)
SCRAPER_DELAY_MIN=2.0        # delay entre requisições
SCRAPER_DELAY_MAX=4.0
```

Com 100 páginas × (2–4 s + fetch), a coleta fica dentro do teto de 15 min da
Lambda no caso típico. Páginas lentas (timeout de 90 s) são risco aceito.

## Execução manual

```bash
cd apps/scraper
# job_daily direto
uv run python -m scheduler.jobs
# caminho da Lambda
uv run python -c "import asyncio, lambda_handler; asyncio.run(lambda_handler.run())"
```

## Migrations

- Lambda **não** roda `alembic upgrade head`.
- Dev local: `main.py` (lifespan do FastAPI) ainda aplica migrations na subida.
- Em produção, migrations devem rodar como **step do pipeline** (GitHub
  Actions) antes do deploy, com falha bloqueando a publicação.

## Testes

`tests/test_lambda_handler.py` cobre o handler com `job_daily` mockado
(retorno de sucesso, falha → `success: 0`, evento EventBridge realista) —
sem rede/OLX.
