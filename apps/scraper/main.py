"""FastAPI app para o serviço Scraper do Imóvel Radar.

Responsabilidades:
- Servir API REST para consulta de listings, alertas e matches
- Rodar scheduler interno (APScheduler) para coleta diária do OLX
- Ser o único proprietário do banco SQLite
"""

from __future__ import annotations

import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

import config
from api.alerts import router as alerts_router
from api.health import router as health_router
from api.listings import router as listings_router
from database import create_tables
from scheduler.setup import start_scheduler, stop_scheduler

# Garante que o diretório raiz do scraper está no sys.path
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=getattr(logging, config.LOG_LEVEL, logging.INFO),
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event do FastAPI: cria tabelas e inicia scheduler."""
    logger.info("Inicializando Scraper...")
    create_tables()
    start_scheduler()
    logger.info("Scraper pronto na porta %s", config.API_PORT)
    yield
    stop_scheduler()
    logger.info("Scraper finalizado.")


app = FastAPI(
    title="Imóvel Radar — Scraper",
    description="API REST do scraper OLX. Proprietário do banco SQLite. "
    "Gerencia listings, alertas e matches.",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(health_router)
app.include_router(listings_router)
app.include_router(alerts_router)