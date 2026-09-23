"""Agregação do painel e o momento em que o snapshot é publicado."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

from shared_models.tables import Listing
from sqlmodel import Session

import lambda_handler
from scheduler.jobs import slices_for_kind
from stats.aggregate import (
    MIN_SAMPLE,
    build_market_snapshot,
    latest_market_snapshot,
    save_market_snapshot,
)


def _listing(listing_id: int, **overrides: object) -> Listing:
    now = datetime.now(UTC)
    values: dict[str, object] = {
        "listing_id": listing_id,
        "url": f"https://exemplo.com/{listing_id}",
        "title": f"Imóvel {listing_id}",
        "municipality": "Maceió",
        "neighbourhood": "Ponta Verde",
        "category": "Apartamentos",
        "images": [],
        "properties": {"size": 50, "rooms": 2, "condominio": 400},
        "price_value": 1500,
        "old_price": None,
        "active": True,
        "listing_kind": "aluguel",
        "first_seen_at": now - timedelta(days=10),
    }
    values.update(overrides)
    return Listing(**values)  # type: ignore[arg-type]


def test_snapshot_median_ignores_other_city_kind_and_outliers(session: Session) -> None:
    prices = [1000 + i * 100 for i in range(MIN_SAMPLE)]
    for index, price in enumerate(prices, start=1):
        extra = {}
        if index == 1:
            extra["old_price"] = price + 500
            extra["first_seen_at"] = datetime.now(UTC)
        session.add(_listing(index, price_value=price, **extra))
    session.add(_listing(100, price_value=50))
    session.add(_listing(101, price_value=9_999, active=False))
    session.add(_listing(102, municipality="Recife", price_value=5_000))
    session.add(_listing(103, listing_kind="venda", price_value=400_000, neighbourhood="Pajuçara"))
    session.add(
        _listing(104, neighbourhood="Farol", price_value=1_200, properties={"size": 40, "rooms": 1})
    )
    session.add(
        _listing(105, neighbourhood="Farol", price_value=1_300, properties={"size": 40, "rooms": 1})
    )
    session.commit()

    payload = build_market_snapshot(session)
    maceio = next(city for city in payload["cities"] if city["key"] == "maceio")
    recife = next(city for city in payload["cities"] if city["key"] == "recife")
    natal = next(city for city in payload["cities"] if city["key"] == "natal")
    rent = maceio["kinds"]["aluguel"]

    assert rent["sample"] == MIN_SAMPLE + 2
    assert rent["median_price"] == 1_600
    assert rent["p25_price"] == 1_300
    assert rent["p75_price"] == 2_000
    assert rent["median_price_m2"] == 32
    assert rent["median_rent_plus_condo"] == 2_100
    assert rent["active_count"] == MIN_SAMPLE + 1 + 2
    assert rent["inactive_count"] == 1
    assert rent["price_drop_count"] == 1
    assert rent["new_count"] == 1
    assert rent["by_category"][0]["category"] == "Apartamentos"
    assert rent["rooms"] == [{"rooms": 1, "sample": 2}, {"rooms": 2, "sample": MIN_SAMPLE}]

    ponta = next(item for item in rent["neighbourhoods"] if item["name"] == "Ponta Verde")
    farol = next(item for item in rent["neighbourhoods"] if item["name"] == "Farol")
    assert ponta["ranked"] is True
    assert ponta["sample"] == MIN_SAMPLE
    assert ponta["median_price"] == 1_700
    assert farol["ranked"] is False
    assert farol["sample"] == 2

    assert recife["kinds"]["aluguel"]["sample"] == 1
    assert recife["kinds"]["aluguel"]["median_price"] == 5_000
    assert natal["municipality"] == "Natal"
    assert maceio["kinds"]["venda"]["sample"] == 1
    assert maceio["kinds"]["venda"]["median_rent_plus_condo"] is None


def test_save_market_snapshot_replaces_same_utc_day(session: Session) -> None:
    moment = datetime(2026, 9, 23, 15, 0, tzinfo=UTC)
    first = build_market_snapshot(session, collected_at=moment)
    save_market_snapshot(session, first)
    session.commit()

    later = build_market_snapshot(session, collected_at=moment.replace(hour=18))
    later["cities"][0]["kinds"]["aluguel"]["sample"] = 99
    save_market_snapshot(session, later)
    session.commit()

    stored = latest_market_snapshot(session)
    assert stored is not None
    assert stored["cities"][0]["kinds"]["aluguel"]["sample"] == 99
    assert stored["min_sample"] == MIN_SAMPLE


def _terminal_result(*, market: str, listing_kind: str, slice_index: int, **extra: object) -> dict:
    last_fields = {
        "success": 1,
        "count": 3,
        "market": market,
        "listing_kind": listing_kind,
        "slice_index": slice_index,
        "completed": True,
        "clamped": False,
        "next_page": None,
        "attempt": 0,
        "run_started_at": "2026-01-01T00:00:00+00:00",
        "deactivated": 0,
    }
    last_fields.update(extra)
    return last_fields


def test_should_publish_only_after_last_natal_sale_slice() -> None:
    natal_last = len(slices_for_kind("venda", "natal")) - 1
    recife_last = len(slices_for_kind("venda", "recife")) - 1
    maceio_last = len(slices_for_kind("venda", "maceio")) - 1

    assert lambda_handler._should_publish_snapshot(
        _terminal_result(market="natal", listing_kind="venda", slice_index=natal_last)
    )
    assert lambda_handler._should_publish_snapshot(
        _terminal_result(
            market="natal",
            listing_kind="venda",
            slice_index=natal_last,
            completed=False,
            clamped=True,
        )
    )
    assert not lambda_handler._should_publish_snapshot(
        _terminal_result(market="recife", listing_kind="venda", slice_index=recife_last)
    )
    assert not lambda_handler._should_publish_snapshot(
        _terminal_result(market="maceio", listing_kind="venda", slice_index=maceio_last)
    )
    assert not lambda_handler._should_publish_snapshot(
        _terminal_result(
            market="natal",
            listing_kind="venda",
            slice_index=natal_last,
            completed=False,
            next_page=None,
        )
    )
    assert not lambda_handler._should_publish_snapshot(
        _terminal_result(market="natal", listing_kind="aluguel", slice_index=0)
    )


def test_run_publishes_snapshot_when_chain_ends(monkeypatch) -> None:
    natal_last = len(slices_for_kind("venda", "natal")) - 1
    published: list[bool] = []

    async def _fake(**kwargs: object) -> dict:
        del kwargs
        return _terminal_result(market="natal", listing_kind="venda", slice_index=natal_last)

    monkeypatch.setattr(lambda_handler, "job_collect_chunk", _fake)
    monkeypatch.setattr(lambda_handler, "publish_market_snapshot", lambda: published.append(True))

    result = asyncio.run(lambda_handler.run({"market": "natal", "listing_kind": "venda"}))

    assert published == [True]
    assert result["snapshot"] == 1


def test_run_skips_snapshot_when_chain_continues(monkeypatch) -> None:
    published: list[bool] = []

    async def _fake(**kwargs: object) -> dict:
        del kwargs
        return _terminal_result(market="maceio", listing_kind="aluguel", slice_index=0)

    monkeypatch.setattr(lambda_handler, "job_collect_chunk", _fake)
    monkeypatch.setattr(lambda_handler, "publish_market_snapshot", lambda: published.append(True))
    monkeypatch.setattr(lambda_handler, "_self_invoke", lambda payload: None)

    result = asyncio.run(lambda_handler.run({}))

    assert published == []
    assert result["snapshot"] == 0


def test_lambda_handler_serves_market_stats(monkeypatch) -> None:
    monkeypatch.setattr(
        "stats.public.market_stats_http_response",
        lambda: {"statusCode": 200, "body": '{"cities":[]}'},
    )

    result = lambda_handler.lambda_handler(
        {
            "rawPath": "/market-stats",
            "requestContext": {"http": {"method": "GET", "path": "/market-stats"}},
        }
    )

    assert result["statusCode"] == 200
