"""Alert intelligence: headlines beyond “novo anúncio”."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from shared_models.tables import ListingAlertMatch

from handlers.alert_intelligence import (
    EventKind,
    classify_listing_event,
    format_drop_amount,
    format_published_ago,
    match_score,
    neighbourhood_median_price,
    prepare_match_carousel,
)

NOW = datetime(2026, 9, 23, 13, 0, tzinfo=UTC)


def _alert(**overrides: object) -> SimpleNamespace:
    values: dict[str, object] = {
        "id": 1,
        "neighbourhoods": ["Ponta Verde"],
        "min_price": 1_500,
        "max_price": 2_500,
        "min_rooms": 2,
        "categories": ["Apartamentos"],
        "listing_kind": "aluguel",
        "municipality": "Maceió",
        "created_at": NOW - timedelta(days=10),
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _listing(**overrides: object) -> SimpleNamespace:
    values: dict[str, object] = {
        "listing_id": 10,
        "title": "Apto Ponta Verde",
        "price_value": 1_800,
        "old_price": None,
        "listing_kind": "aluguel",
        "municipality": "Maceió",
        "neighbourhood": "Ponta Verde",
        "properties": {"rooms": 2, "condominio": 0, "iptu": 0},
        "first_seen_at": NOW - timedelta(hours=2),
        "active": True,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _snapshot(*, median: int = 2_200, ranked: bool = True) -> dict:
    return {
        "cities": [
            {
                "municipality": "Maceió",
                "kinds": {
                    "aluguel": {
                        "neighbourhoods": [
                            {
                                "name": "Ponta Verde",
                                "median_price": median,
                                "ranked": ranked,
                            }
                        ]
                    }
                },
            }
        ]
    }


def test_format_drop_amount_uses_mil_for_round_thousands() -> None:
    assert format_drop_amount(30_000) == "R$ 30 mil"
    assert format_drop_amount(200) == "R$ 200"


def test_format_published_ago_minutes_and_hours() -> None:
    assert format_published_ago(NOW - timedelta(minutes=8), NOW) == "há 8 minutos"
    assert format_published_ago(NOW - timedelta(hours=2), NOW) == "há 2 horas"


def test_price_drop_beats_other_signals() -> None:
    listing = _listing(old_price=2_100, price_value=1_800)
    event = classify_listing_event(
        listing,  # type: ignore[arg-type]
        _alert(),  # type: ignore[arg-type]
        snapshot=_snapshot(),
        now=NOW,
    )
    assert event.kind == EventKind.PRICE_DROP
    assert event.headline == "📉 Preço caiu R$ 300"


def test_sale_price_drop_uses_mil() -> None:
    listing = _listing(
        listing_kind="venda",
        price_value=270_000,
        old_price=300_000,
        first_seen_at=NOW - timedelta(days=5),
    )
    event = classify_listing_event(
        listing,  # type: ignore[arg-type]
        _alert(min_price=200_000, max_price=350_000),  # type: ignore[arg-type]
        now=NOW,
    )
    assert event.kind == EventKind.PRICE_DROP
    assert event.headline == "📉 Preço caiu R$ 30 mil"


def test_tiny_rent_drop_is_ignored() -> None:
    listing = _listing(old_price=1_820, price_value=1_800)
    event = classify_listing_event(
        listing,  # type: ignore[arg-type]
        _alert(),  # type: ignore[arg-type]
        snapshot=None,
        now=NOW,
    )
    assert event.kind != EventKind.PRICE_DROP


def test_back_on_market_for_old_alert_and_old_listing() -> None:
    listing = _listing(first_seen_at=NOW - timedelta(days=20), old_price=None)
    event = classify_listing_event(
        listing,  # type: ignore[arg-type]
        _alert(created_at=NOW - timedelta(days=10)),  # type: ignore[arg-type]
        snapshot=None,
        now=NOW,
    )
    assert event.kind == EventKind.BACK_ON_MARKET
    assert event.headline == "👀 Esse imóvel voltou a ficar disponível"


def test_new_alert_seed_is_not_back_on_market() -> None:
    listing = _listing(first_seen_at=NOW - timedelta(days=20))
    event = classify_listing_event(
        listing,  # type: ignore[arg-type]
        _alert(created_at=NOW - timedelta(minutes=5)),  # type: ignore[arg-type]
        snapshot=None,
        now=NOW,
    )
    assert event.kind != EventKind.BACK_ON_MARKET


def test_below_neighbourhood_median() -> None:
    listing = _listing(
        price_value=1_800,
        first_seen_at=NOW - timedelta(hours=2),
        properties={"rooms": 2},
    )
    # Faixa larga para o match ficar < 90; o preço ainda está ~18% abaixo da mediana.
    event = classify_listing_event(
        listing,  # type: ignore[arg-type]
        _alert(min_price=1_000, max_price=3_500, neighbourhoods=None, categories=None),  # type: ignore[arg-type]
        snapshot=_snapshot(median=2_200),
        now=NOW,
    )
    assert event.kind == EventKind.BELOW_AVERAGE
    assert event.headline == "🏷️ Preço abaixo da média da região"


def test_unranked_neighbourhood_skips_below_average() -> None:
    listing = _listing(first_seen_at=NOW - timedelta(days=2), price_value=1_800)
    median = neighbourhood_median_price(
        _snapshot(ranked=False),
        municipality="Maceió",
        listing_kind="aluguel",
        neighbourhood="Ponta Verde",
    )
    assert median is None
    event = classify_listing_event(
        listing,  # type: ignore[arg-type]
        _alert(neighbourhoods=None, categories=None, min_price=1_000, max_price=3_500),  # type: ignore[arg-type]
        snapshot=_snapshot(ranked=False),
        now=NOW,
    )
    assert event.kind != EventKind.BELOW_AVERAGE


def test_high_match_headline() -> None:
    listing = _listing(
        price_value=1_550,
        first_seen_at=NOW - timedelta(hours=2),
        properties={"rooms": 3},
    )
    score = match_score(listing, _alert())  # type: ignore[arg-type]
    assert score >= 90
    event = classify_listing_event(
        listing,  # type: ignore[arg-type]
        _alert(),  # type: ignore[arg-type]
        snapshot=None,
        now=NOW,
    )
    assert event.kind == EventKind.HIGH_MATCH
    assert event.headline == f"🔥 Novo imóvel com {score}% de match"


def test_fresh_listing_uses_relative_time() -> None:
    listing = _listing(
        price_value=2_400,
        first_seen_at=NOW - timedelta(minutes=8),
        properties={"rooms": 2},
    )
    event = classify_listing_event(
        listing,  # type: ignore[arg-type]
        _alert(neighbourhoods=None, categories=None, min_rooms=None),  # type: ignore[arg-type]
        snapshot=None,
        now=NOW,
    )
    assert event.kind == EventKind.FRESH
    assert event.headline == "⚡ Anúncio publicado há 8 minutos"


def test_carousel_sorts_price_drop_first() -> None:
    drop = _listing(listing_id=1, old_price=2_200, price_value=1_800)
    fresh = _listing(
        listing_id=2,
        price_value=2_400,
        old_price=None,
        first_seen_at=NOW - timedelta(minutes=8),
        properties={"rooms": 2},
    )
    alert = _alert()
    rows = [
        ListingAlertMatch(listing=fresh, alert_id=1),  # type: ignore[arg-type]
        ListingAlertMatch(listing=drop, alert_id=1),  # type: ignore[arg-type]
    ]
    listings, headlines = prepare_match_carousel(
        rows,
        [alert],  # type: ignore[arg-type]
        None,
        now=NOW,
    )
    assert listings[0].listing_id == 1
    assert headlines[0].startswith("📉 Preço caiu")
    assert headlines[1].startswith("⚡ Anúncio publicado")
