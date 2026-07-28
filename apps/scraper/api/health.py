"""Endpoint de healthcheck para o scraper."""

from __future__ import annotations

from fastapi import APIRouter

from database import get_connection
from shared_models.api_schemas import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Retorna status do serviço e contagens básicas do banco."""
    conn = get_connection()
    try:
        listings_count = conn.execute("SELECT COUNT(*) FROM listings").fetchone()[0]
        alerts_count = conn.execute("SELECT COUNT(*) FROM alerts").fetchone()[0]
    finally:
        conn.close()

    return HealthResponse(status="ok", listings_count=listings_count, alerts_count=alerts_count)