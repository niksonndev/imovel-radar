"""FastAPI app para o scraper em dev local (health + migrations).

Produção: coleta via Lambda (``lambda_handler.py``), sem FastAPI. Users/alerts
são da bot (ADR 0005) — a API REST desses recursos foi removida.
"""

from __future__ import annotations

import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from alembic.config import Config
from fastapi import FastAPI

import config
from alembic import command
from api.health import router as health_router
from api.market_stats import router as market_stats_router

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _run_migrations() -> None:
    """Aplica as migrações Alembic na subida (idempotente)."""
    cfg = Config(str(ROOT / "alembic.ini"))
    command.upgrade(cfg, "head")


logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=getattr(logging, config.LOG_LEVEL, logging.INFO),
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event do FastAPI: aplica migrações (dev local)."""
    logger.info("Inicializando Scraper...")
    _run_migrations()
    logger.info("Scraper pronto na porta %s", config.API_PORT)
    yield
    logger.info("Scraper finalizado.")


app = FastAPI(
    title="Imóvel Radar — Scraper",
    description="Coleta OLX e persiste ``listing``. Healthcheck para o compose local.",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(health_router)
app.include_router(market_stats_router)
