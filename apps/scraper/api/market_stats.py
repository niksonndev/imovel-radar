"""GET local do snapshot. Em produção o mesmo JSON sai pela Lambda."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlmodel import Session

from database import get_session
from stats.aggregate import latest_market_snapshot

router = APIRouter(tags=["market"])


@router.get("/market-stats")
def market_stats(session: Session = Depends(get_session)) -> JSONResponse:
    payload: dict[str, Any] | None = latest_market_snapshot(session)
    if payload is None:
        raise HTTPException(status_code=404, detail="snapshot indisponível")
    return JSONResponse(
        payload,
        headers={"Cache-Control": "public, max-age=3600"},
    )
