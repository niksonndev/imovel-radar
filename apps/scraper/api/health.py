"""Endpoint de healthcheck para o scraper."""

from __future__ import annotations

from typing import Literal, TypedDict

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from database import get_session

router = APIRouter(tags=["health"])


class HealthResponse(TypedDict):
    status: Literal["ok"]


@router.get("/health")
async def health(session: Session = Depends(get_session)) -> HealthResponse:
    session.exec(select(1)).one()
    return {"status": "ok"}
