"""Consultas da Bot Lambda no Postgres compartilhado (ADR 0005).

A bot lê ``listing`` (read-only), escreve ``users``/``alerts``/``alert_matches``/
``watched_listings``. O commit/rollback fica com o chamador.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from typing import Literal

from shared_models.tables import (
    Alert,
    AlertMatch,
    Listing,
    ListingAlertMatch,
    ListingKind,
    User,
    WatchedListing,
    WatchedListingChange,
)
from shared_models.utils import effective_listing_price
from sqlalchemy import Integer, case, cast, delete, func, or_
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlmodel import Session, select

import config


# ── Users (dona: bot) ──────────────────────────────────────────────────────
def ensure_user(session: Session, chat_id: int) -> bool:
    """Garante a existência do usuário; cria se necessário (idempotente).

    Não commita — o chamador decide quando persistir.
    """
    stmt = postgres_insert(User).values(chat_id=chat_id).on_conflict_do_nothing()
    result = session.exec(stmt)
    return result.rowcount is not None  # True mesmo se nada inserido


def get_user(session: Session, chat_id: int) -> User | None:
    return session.get(User, chat_id)


def is_pro(user: User | None) -> bool:
    """Entitlement Pro: plan=pro e ``pro_until`` no futuro (ou sem expiry)."""
    if user is None or user.plan != "pro":
        return False
    if user.pro_until is None:
        return True
    until = user.pro_until
    if until.tzinfo is None:
        until = until.replace(tzinfo=UTC)
    return until > datetime.now(UTC)


def watch_cap_for(user: User | None) -> int:
    return config.WATCHLIST_PRO_CAP if is_pro(user) else config.WATCHLIST_FREE_CAP


def alert_cap_for(user: User | None) -> int:
    return config.ALERT_PRO_CAP if is_pro(user) else config.ALERT_FREE_CAP


def activate_pro(
    session: Session,
    *,
    chat_id: int,
    pro_until: datetime | None,
    telegram_payment_charge_id: str | None,
    subscription_active: bool = True,
) -> User:
    """Ativa ou renova Radar Pro. Garante a linha do usuário."""
    ensure_user(session, chat_id)
    user = get_user(session, chat_id)
    if user is None:
        raise RuntimeError(f"Usuário {chat_id} não encontrado após ensure_user")
    user.plan = "pro"
    user.pro_until = pro_until
    if telegram_payment_charge_id:
        user.stars_telegram_payment_charge_id = telegram_payment_charge_id
    user.stars_subscription_active = subscription_active
    session.add(user)
    session.flush()
    return user


def mark_pro_subscription_canceled(session: Session, chat_id: int) -> User | None:
    """Marca assinatura cancelada; mantém Pro até ``pro_until``."""
    user = get_user(session, chat_id)
    if user is None:
        return None
    user.stars_subscription_active = False
    session.add(user)
    session.flush()
    return user


def downgrade_expired_pro(session: Session, chat_id: int) -> User | None:
    """Se Pro expirou, volta para free."""
    user = get_user(session, chat_id)
    if user is None or is_pro(user):
        return user
    if user.plan == "pro":
        user.plan = "free"
        user.stars_subscription_active = False
        session.add(user)
        session.flush()
    return user


_EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$")


def normalize_email(raw: str) -> str | None:
    """Lowercase + strip; ``None`` se formato inválido."""
    email = (raw or "").strip().lower()
    if not email or _EMAIL_RE.match(email) is None:
        return None
    return email


ClaimEmailProTrialStatus = Literal[
    "activated",
    "already_pro",
    "already_claimed",
    "email_taken",
    "invalid_email",
]


def claim_email_pro_trial(
    session: Session,
    *,
    chat_id: int,
    email_raw: str,
) -> tuple[ClaimEmailProTrialStatus, User | None]:
    """Cadastro de e-mail → 1 mês de Radar Pro (uma vez por usuário)."""
    email = normalize_email(email_raw)
    if email is None:
        return "invalid_email", None

    ensure_user(session, chat_id)
    user = get_user(session, chat_id)
    if user is None:
        raise RuntimeError(f"Usuário {chat_id} não encontrado após ensure_user")

    if is_pro(user):
        return "already_pro", user
    if user.email_pro_trial_claimed_at is not None:
        return "already_claimed", user

    taken = session.exec(
        select(User).where(User.email == email, User.chat_id != chat_id)
    ).first()
    if taken is not None:
        return "email_taken", None

    now = datetime.now(UTC)
    pro_until = now + timedelta(days=config.EMAIL_PRO_TRIAL_DAYS)
    user = activate_pro(
        session,
        chat_id=chat_id,
        pro_until=pro_until,
        telegram_payment_charge_id=None,
        subscription_active=False,
    )
    user.email = email
    user.email_pro_trial_claimed_at = now
    session.add(user)
    session.flush()
    return "activated", user


def get_users_chat_ids(session: Session) -> list[int]:
    """Todos os chat_ids cadastrados (para o job de notificação)."""
    return list(session.exec(select(User.chat_id)).all())


# ── Neighbourhoods (lê listing) ────────────────────────────────────────────
def get_neighbourhoods(
    session: Session,
    municipality: str = "Maceió",
    *,
    listing_kind: ListingKind | None = None,
) -> list[str]:
    conditions = [
        Listing.municipality == municipality,
        Listing.neighbourhood != "",
    ]
    if listing_kind is not None:
        conditions.append(Listing.listing_kind == listing_kind)
    return list(
        session.exec(
            select(Listing.neighbourhood)
            .where(*conditions)
            .group_by(Listing.neighbourhood)
            .order_by(func.count().desc())
        ).all()
    )


# ── Listings (read-only) ───────────────────────────────────────────────────
def get_listing(session: Session, listing_id: int) -> Listing | None:
    return session.get(Listing, listing_id)


# ── Alerts (dona: bot) ─────────────────────────────────────────────────────
def create_alert(
    session: Session,
    *,
    chat_id: int,
    alert_name: str | None,
    min_price: int | None,
    max_price: int | None,
    neighbourhoods: list[str] | None,
    listing_kind: ListingKind = "aluguel",
    min_rooms: int | None = None,
    categories: list[str] | None = None,
) -> int:
    """Cria um alerta e retorna o id (o chamador decide quando commitar)."""
    alert = Alert(
        chat_id=chat_id,
        alert_name=alert_name,
        listing_kind=listing_kind,
        min_price=min_price,
        max_price=max_price,
        min_rooms=min_rooms,
        neighbourhoods=neighbourhoods,
        categories=categories,
    )
    session.add(alert)
    session.flush()  # preenche id sem commitar
    if alert.id is None:
        raise RuntimeError("Falha ao obter ID do alerta inserido")
    return alert.id


def find_equivalent_alert(
    session: Session,
    *,
    chat_id: int,
    min_price: int | None,
    max_price: int | None,
    neighbourhoods: list[str] | None,
    listing_kind: ListingKind = "aluguel",
    min_rooms: int | None = None,
    categories: list[str] | None = None,
) -> Alert | None:
    """Alerta já existente do usuário com os mesmos filtros (nome ignorado)."""
    wanted_nb = sorted(neighbourhoods or [])
    wanted_cats = sorted(categories or [])
    for alert in get_alerts_for_user(session, chat_id):
        if (
            alert.listing_kind == listing_kind
            and alert.min_price == min_price
            and alert.max_price == max_price
            and alert.min_rooms == min_rooms
            and sorted(alert.neighbourhoods or []) == wanted_nb
            and sorted(alert.categories or []) == wanted_cats
        ):
            return alert
    return None


def get_alerts_for_user(session: Session, chat_id: int) -> list[Alert]:
    return list(
        session.exec(select(Alert).where(Alert.chat_id == chat_id).order_by(Alert.id.desc())).all()  # type: ignore[union-attr]
    )


def get_active_alerts_for_user(session: Session, chat_id: int) -> list[Alert]:
    return list(
        session.exec(
            select(Alert)
            .where(Alert.chat_id == chat_id, Alert.active.is_(True))  # type: ignore[union-attr]
            .order_by(Alert.id.desc())  # type: ignore[union-attr]
        ).all()
    )


def count_active_alerts_for_user(session: Session, chat_id: int) -> int:
    return int(
        session.exec(
            select(func.count())
            .select_from(Alert)
            .where(Alert.chat_id == chat_id, Alert.active.is_(True))  # type: ignore[union-attr]
        ).one()
    )


def get_alert_for_user(session: Session, chat_id: int, alert_id: int) -> Alert | None:
    return session.exec(
        select(Alert).where(Alert.id == alert_id, Alert.chat_id == chat_id)
    ).one_or_none()


def delete_alert_for_user(session: Session, chat_id: int, alert_id: int) -> bool:
    alert = session.exec(
        select(Alert).where(Alert.id == alert_id, Alert.chat_id == chat_id)
    ).first()
    if alert is None:
        return False
    session.exec(delete(AlertMatch).where(AlertMatch.alert_id == alert_id))  # type: ignore[union-attr]
    session.delete(alert)
    return True


def _json_fee(key: str):
    """Condomínio/IPTU do JSON. Ausente, nulo ou ≤ 0 conta como zero."""
    raw = cast(Listing.properties[key].as_string(), Integer)
    return func.coalesce(func.greatest(raw, 0), 0)


def effective_price_expr():
    """Aluguel + condomínio + IPTU. Venda permanece o preço pedido."""
    fees = _json_fee("condominio") + _json_fee("iptu")
    return case(
        (Listing.listing_kind == "aluguel", Listing.price_value + fees),
        else_=Listing.price_value,
    )


def _baseline_price(listing: Listing) -> int | None:
    props = listing.properties if isinstance(listing.properties, dict) else {}
    return effective_listing_price(
        listing.price_value,
        listing_kind=listing.listing_kind,
        condominio=props.get("condominio"),
        iptu=props.get("iptu"),
    )


# ── Match / notificação (lê listing, escreve alert_matches) ────────────────
def get_unnotified_listings_for_alert(session: Session, alert: Alert) -> list[Listing]:
    conditions = [
        Listing.active.is_(True),  # type: ignore[union-attr]
        Listing.listing_kind == alert.listing_kind,
        AlertMatch.listing_id.is_(None),  # type: ignore[union-attr]
    ]
    if (min_price := alert.min_price) is not None:
        conditions.append(effective_price_expr() >= min_price)
    if (max_price := alert.max_price) is not None:
        conditions.append(effective_price_expr() <= max_price)
    if (min_rooms := alert.min_rooms) is not None:
        rooms = cast(Listing.properties["rooms"].as_string(), Integer)
        conditions.append(or_(rooms.is_(None), rooms >= min_rooms))
    if alert.categories:
        conditions.append(Listing.category.in_(alert.categories))  # type: ignore[union-attr]
    if alert.neighbourhoods:
        conditions.append(Listing.neighbourhood.in_(alert.neighbourhoods))  # type: ignore[union-attr]

    stmt = (
        select(Listing)
        .outerjoin(
            AlertMatch,
            (AlertMatch.listing_id == Listing.listing_id) & (AlertMatch.alert_id == alert.id),  # type: ignore[union-attr]
        )
        .where(*conditions)
        .order_by(Listing.updated_at.desc())  # type: ignore[union-attr]
    )
    return list(session.exec(stmt).all())


def get_unnotified_listings_for_user(session: Session, chat_id: int) -> list[ListingAlertMatch]:
    """Listings ainda não notificados para os alertas ativos de um usuário."""
    result: list[ListingAlertMatch] = []
    for alert in get_active_alerts_for_user(session, chat_id):
        if alert.id is None:
            continue
        for listing in get_unnotified_listings_for_alert(session, alert):
            result.append(ListingAlertMatch(listing=listing, alert_id=alert.id))
    return result


def mark_listings_notified(session: Session, pairs: list[tuple[int, int]]) -> None:
    """Registra pares (alert_id, listing_id) como notificados (idempotente)."""
    if not pairs:
        return
    stmt = (
        postgres_insert(AlertMatch)
        .values(
            [
                {"alert_id": alert_id, "listing_id": listing_id}
                for alert_id, listing_id in pairs
            ]
        )
        .on_conflict_do_nothing(index_elements=["alert_id", "listing_id"])
    )
    session.exec(stmt)  # type: ignore[call-overload]


# ── Watchlist (dona: bot) ──────────────────────────────────────────────────
def count_watches_for_user(session: Session, chat_id: int) -> int:
    return int(
        session.exec(
            select(func.count())
            .select_from(WatchedListing)
            .where(WatchedListing.chat_id == chat_id)
        ).one()
    )


def get_watches_for_user(session: Session, chat_id: int) -> list[WatchedListingChange]:
    """Watches do usuário com o listing atual (mais recentes primeiro)."""
    rows = session.exec(
        select(WatchedListing, Listing)
        .join(Listing, Listing.listing_id == WatchedListing.listing_id)
        .where(WatchedListing.chat_id == chat_id)
        .order_by(WatchedListing.id.desc())  # type: ignore[union-attr]
    ).all()
    return [WatchedListingChange(watch=w, listing=listing) for w, listing in rows]


def get_watch_for_user(
    session: Session, chat_id: int, watch_id: int
) -> WatchedListingChange | None:
    row = session.exec(
        select(WatchedListing, Listing)
        .join(Listing, Listing.listing_id == WatchedListing.listing_id)
        .where(WatchedListing.id == watch_id, WatchedListing.chat_id == chat_id)
    ).one_or_none()
    if row is None:
        return None
    watch, listing = row
    return WatchedListingChange(watch=watch, listing=listing)


def get_watch_by_listing(
    session: Session, chat_id: int, listing_id: int
) -> WatchedListing | None:
    return session.exec(
        select(WatchedListing).where(
            WatchedListing.chat_id == chat_id,
            WatchedListing.listing_id == listing_id,
        )
    ).one_or_none()


def create_watch(session: Session, *, chat_id: int, listing_id: int) -> tuple[str, int | None]:
    """Cria acompanhamento. Retorna ``(status, watch_id)``.

    status: ``created`` | ``duplicate`` | ``cap_reached`` | ``listing_missing``
    """
    listing = get_listing(session, listing_id)
    if listing is None:
        return "listing_missing", None

    existing = get_watch_by_listing(session, chat_id, listing_id)
    if existing is not None:
        return "duplicate", existing.id

    if count_watches_for_user(session, chat_id) >= watch_cap_for(get_user(session, chat_id)):
        return "cap_reached", None

    watch = WatchedListing(
        chat_id=chat_id,
        listing_id=listing_id,
        last_known_price=_baseline_price(listing),
        last_known_active=listing.active,
    )
    session.add(watch)
    session.flush()
    if watch.id is None:
        raise RuntimeError("Falha ao obter ID do acompanhamento inserido")
    return "created", watch.id


def delete_watch_for_user(session: Session, chat_id: int, watch_id: int) -> bool:
    watch = session.exec(
        select(WatchedListing).where(
            WatchedListing.id == watch_id,
            WatchedListing.chat_id == chat_id,
        )
    ).first()
    if watch is None:
        return False
    session.delete(watch)
    return True


def get_changed_watches(session: Session) -> list[WatchedListingChange]:
    """Watches cujo listing mudou de preço ou status ativo desde o baseline."""
    rows = session.exec(
        select(WatchedListing, Listing)
        .join(Listing, Listing.listing_id == WatchedListing.listing_id)
        .where(
            or_(
                effective_price_expr().is_distinct_from(WatchedListing.last_known_price),
                Listing.active.is_distinct_from(WatchedListing.last_known_active),
            )
        )
        .order_by(WatchedListing.chat_id, WatchedListing.id)
    ).all()
    return [WatchedListingChange(watch=w, listing=listing) for w, listing in rows]


def update_watch_baselines(
    session: Session,
    updates: list[tuple[int, int | None, bool]],
) -> None:
    """Atualiza baselines ``(watch_id, price, active)`` após notificar."""
    if not updates:
        return
    for watch_id, price, active in updates:
        watch = session.get(WatchedListing, watch_id)
        if watch is None:
            continue
        watch.last_known_price = price
        watch.last_known_active = active
        session.add(watch)
