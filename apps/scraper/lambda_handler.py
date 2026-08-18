"""Entry point AWS Lambda para o scraper (trigger: EventBridge).

Executa apenas a coleta diária do OLX + persistência no Postgres (reusa
``job_daily``). Nunca roda migrations (Alembic é step do pipeline — ADR 0004)
e não importa o app FastAPI (sem uvicorn no runtime).

Run manual/local (mesmo caminho da Lambda):
    uv run python -m scheduler.jobs
    uv run python -c "import asyncio, lambda_handler; asyncio.run(lambda_handler.run())"
"""

from __future__ import annotations

import asyncio
import logging

import config
from scheduler.jobs import job_daily

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=getattr(logging, config.LOG_LEVEL, logging.INFO),
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


async def run() -> dict[str, int]:
    """Executa a coleção diária e retorna ``{"success", "count"}``."""
    return await job_daily()


def lambda_handler(event: dict | None, context: object | None = None) -> dict[str, int]:
    """Handler AWS Lambda (trigger EventBridge)."""
    del event, context  # gatilho único; o payload não influencia
    try:
        return asyncio.run(run())
    except Exception:
        logger.exception("Lambda collection failed")
        return {"success": 0, "count": 0}
