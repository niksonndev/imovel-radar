"""Grava o snapshot do dia. Chamado só no fim da cadeia Maceió → Recife."""

from __future__ import annotations

from sqlmodel import Session

from database import engine
from stats.aggregate import build_market_snapshot, save_market_snapshot


def publish_market_snapshot() -> None:
    with Session(engine) as session:
        payload = build_market_snapshot(session)
        save_market_snapshot(session, payload)
        session.commit()
