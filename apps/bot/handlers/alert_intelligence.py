"""Classifica o *porquê* de um match — não só “novo anúncio”.

A coleta é diária, então “publicado há 8 minutos” só aparece quando
``first_seen_at`` é de fato recente. Queda de preço, volta ao ar e
preço abaixo da mediana da região têm prioridade porque quase todo
match novo também é “recente”.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import IntEnum, StrEnum
from typing import Any, Protocol

from shared_models.tables import Alert, Listing, ListingAlertMatch
from shared_models.utils import effective_listing_price, format_brl

FRESH_WINDOW = timedelta(hours=36)
HIGH_MATCH_MIN = 90
BELOW_AVG_RATIO = 0.95
RENT_MIN_DROP = 50
SALE_MIN_DROP = 1_000


class EventKind(StrEnum):
    PRICE_DROP = "price_drop"
    BACK_ON_MARKET = "back_on_market"
    BELOW_AVERAGE = "below_average"
    HIGH_MATCH = "high_match"
    FRESH = "fresh"
    NEW = "new"


class EventPriority(IntEnum):
    """Menor = aparece primeiro no carrossel (sinal mais forte)."""

    PRICE_DROP = 0
    BACK_ON_MARKET = 1
    BELOW_AVERAGE = 2
    HIGH_MATCH = 3
    FRESH = 4
    NEW = 5


_PRIORITY = {
    EventKind.PRICE_DROP: EventPriority.PRICE_DROP,
    EventKind.BACK_ON_MARKET: EventPriority.BACK_ON_MARKET,
    EventKind.BELOW_AVERAGE: EventPriority.BELOW_AVERAGE,
    EventKind.HIGH_MATCH: EventPriority.HIGH_MATCH,
    EventKind.FRESH: EventPriority.FRESH,
    EventKind.NEW: EventPriority.NEW,
}


@dataclass(frozen=True)
class AlertEvent:
    kind: EventKind
    headline: str
    match_pct: int


class _AlertLike(Protocol):
    neighbourhoods: list[str] | None
    min_price: int | None
    max_price: int | None
    min_rooms: int | None
    categories: list[str] | None
    created_at: datetime | None


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def _now(now: datetime | None) -> datetime:
    if now is None:
        return datetime.now(UTC)
    return _aware(now) or datetime.now(UTC)


def _props(listing: Listing) -> dict[str, Any]:
    raw = listing.properties
    return raw if isinstance(raw, dict) else {}


def _asked_price(listing: Listing) -> int | None:
    return listing.price_value if isinstance(listing.price_value, int) else None


def _total_price(listing: Listing) -> int | None:
    props = _props(listing)
    return effective_listing_price(
        listing.price_value,
        listing_kind=getattr(listing, "listing_kind", None) or "aluguel",
        condominio=props.get("condominio"),
        iptu=props.get("iptu"),
    )


def format_drop_amount(amount: int) -> str:
    """R$ 30.000 → ``R$ 30 mil``; valores menores ficam em reais."""
    if amount >= 1000 and amount % 1000 == 0:
        return f"R$ {amount // 1000} mil"
    formatted = format_brl(amount)
    return formatted[:-3] if formatted.endswith(",00") else formatted


def format_published_ago(first_seen_at: datetime, now: datetime) -> str:
    start = _aware(first_seen_at)
    moment = _aware(now)
    if start is None or moment is None:
        return "há pouco"
    seconds = max(0, int((moment - start).total_seconds()))
    minutes = seconds // 60
    hours = minutes // 60
    days = hours // 24
    if minutes < 1:
        return "há instantes"
    if minutes == 1:
        return "há 1 minuto"
    if minutes < 60:
        return f"há {minutes} minutos"
    if hours == 1:
        return "há 1 hora"
    if hours < 24:
        return f"há {hours} horas"
    if days == 1:
        return "ontem"
    return f"há {days} dias"


def match_score(listing: Listing, alert: _AlertLike) -> int:
    """0–100. Filtros do alerta já passaram; mede o quão boa é a combinação."""
    price = _total_price(listing)
    min_price = alert.min_price
    max_price = alert.max_price

    if price is None:
        price_pts = 20.0
    elif max_price is not None and min_price is not None:
        span = max(max_price - min_price, 1)
        t = min(max((price - min_price) / span, 0.0), 1.0)
        price_pts = 45.0 - 30.0 * t
    elif max_price is not None:
        floor = 0.7 * max_price
        span = max(max_price - floor, 1.0)
        t = min(max((price - floor) / span, 0.0), 1.0)
        price_pts = 45.0 - 30.0 * t
    else:
        price_pts = 30.0

    neighbourhoods = alert.neighbourhoods or []
    nbhd_pts = 25.0 if neighbourhoods else 12.0

    rooms_raw = _props(listing).get("rooms")
    rooms = rooms_raw if isinstance(rooms_raw, int) else None
    min_rooms = alert.min_rooms
    if min_rooms is None:
        rooms_pts = 12.0 if rooms is not None else 8.0
    elif rooms is None:
        rooms_pts = 8.0
    elif rooms > min_rooms:
        rooms_pts = 18.0
    else:
        rooms_pts = 14.0

    cat_pts = 12.0 if alert.categories else 6.0
    return int(round(price_pts + nbhd_pts + rooms_pts + cat_pts))


def neighbourhood_median_price(
    snapshot: dict[str, Any] | None,
    *,
    municipality: str,
    listing_kind: str,
    neighbourhood: str,
) -> int | None:
    """Mediana do bairro no snapshot do scraper, só com amostra ranqueada."""
    if not snapshot or not neighbourhood:
        return None
    cities = snapshot.get("cities")
    if not isinstance(cities, list):
        return None
    for city in cities:
        if not isinstance(city, dict) or city.get("municipality") != municipality:
            continue
        kinds = city.get("kinds")
        if not isinstance(kinds, dict):
            return None
        kind_stats = kinds.get(listing_kind)
        if not isinstance(kind_stats, dict):
            return None
        rows = kind_stats.get("neighbourhoods")
        if not isinstance(rows, list):
            return None
        for row in rows:
            if not isinstance(row, dict) or row.get("name") != neighbourhood:
                continue
            if row.get("ranked") is not True:
                return None
            median = row.get("median_price")
            return int(median) if isinstance(median, int) else None
        return None
    return None


def _price_drop_amount(listing: Listing) -> int | None:
    old_price = listing.old_price if isinstance(listing.old_price, int) else None
    new_price = _asked_price(listing)
    if old_price is None or new_price is None or old_price <= new_price:
        return None
    drop = old_price - new_price
    kind = getattr(listing, "listing_kind", None) or "aluguel"
    minimum = SALE_MIN_DROP if kind == "venda" else RENT_MIN_DROP
    return drop if drop >= minimum else None


def _is_fresh(listing: Listing, now: datetime) -> bool:
    first_seen = _aware(listing.first_seen_at)
    if first_seen is None:
        return False
    return now - first_seen <= FRESH_WINDOW


def _is_back_on_market(listing: Listing, alert: _AlertLike, now: datetime) -> bool:
    """Alerta antigo + anúncio antigo que só agora entrou na fila de notificação.

    ``alert_matches`` só grava ativo+match. Se o anúncio ficou fora do ar
    (ou fora do filtro) e voltou, chega como unnotified com ``first_seen_at`` velho.
    """
    created = _aware(alert.created_at)
    first_seen = _aware(listing.first_seen_at)
    if created is None or first_seen is None:
        return False
    if now - created < FRESH_WINDOW:
        return False
    if now - first_seen < FRESH_WINDOW:
        return False
    return True


def classify_listing_event(
    listing: Listing,
    alert: _AlertLike,
    *,
    snapshot: dict[str, Any] | None = None,
    now: datetime | None = None,
) -> AlertEvent:
    moment = _now(now)
    score = match_score(listing, alert)
    drop = _price_drop_amount(listing)
    if drop is not None:
        return AlertEvent(
            kind=EventKind.PRICE_DROP,
            headline=f"📉 Preço caiu {format_drop_amount(drop)}",
            match_pct=score,
        )
    if _is_back_on_market(listing, alert, moment):
        return AlertEvent(
            kind=EventKind.BACK_ON_MARKET,
            headline="👀 Esse imóvel voltou a ficar disponível",
            match_pct=score,
        )

    asked = _asked_price(listing)
    median = neighbourhood_median_price(
        snapshot,
        municipality=getattr(listing, "municipality", None) or "",
        listing_kind=getattr(listing, "listing_kind", None) or "aluguel",
        neighbourhood=listing.neighbourhood or "",
    )
    if asked is not None and median is not None and asked <= int(median * BELOW_AVG_RATIO):
        return AlertEvent(
            kind=EventKind.BELOW_AVERAGE,
            headline="🏷️ Preço abaixo da média da região",
            match_pct=score,
        )
    if score >= HIGH_MATCH_MIN:
        return AlertEvent(
            kind=EventKind.HIGH_MATCH,
            headline=f"🔥 Novo imóvel com {score}% de match",
            match_pct=score,
        )
    if _is_fresh(listing, moment):
        ago = format_published_ago(listing.first_seen_at or moment, moment)
        return AlertEvent(
            kind=EventKind.FRESH,
            headline=f"⚡ Anúncio publicado {ago}",
            match_pct=score,
        )
    return AlertEvent(
        kind=EventKind.NEW,
        headline="🚨 Novo imóvel encontrado",
        match_pct=score,
    )


def prepare_match_carousel(
    rows: Sequence[ListingAlertMatch],
    alerts: Sequence[Alert],
    snapshot: dict[str, Any] | None,
    *,
    now: datetime | None = None,
) -> tuple[list[Listing], list[str]]:
    """Ordena matches pelo sinal mais forte e devolve headlines alinhadas."""
    alerts_by_id = {alert.id: alert for alert in alerts if alert.id is not None}
    moment = _now(now)
    scored: list[tuple[int, int, int, Listing, str]] = []
    for index, row in enumerate(rows):
        alert = alerts_by_id.get(row.alert_id)
        if alert is None:
            event = AlertEvent(
                kind=EventKind.NEW,
                headline="🚨 Novo imóvel encontrado",
                match_pct=0,
            )
        else:
            event = classify_listing_event(
                row.listing, alert, snapshot=snapshot, now=moment
            )
        listing_id = getattr(row.listing, "listing_id", 0) or 0
        scored.append(
            (
                int(_PRIORITY[event.kind]),
                -event.match_pct,
                listing_id if isinstance(listing_id, int) else index,
                row.listing,
                event.headline,
            )
        )
    scored.sort(key=lambda item: (item[0], item[1], item[2]))
    listings = [item[3] for item in scored]
    headlines = [item[4] for item in scored]
    return listings, headlines
