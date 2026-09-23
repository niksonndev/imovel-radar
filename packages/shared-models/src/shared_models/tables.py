"""SQLModel table models do Postgres compartilhado — fonte única do schema físico.

Usados por scraper e bot (ADR 0005): a bot é dona de ``users``, ``alerts``,
``alert_matches`` e ``watched_listings`` e lê ``listing`` (read-only); o scraper
é dono de ``listing``.

Atenção: as classes registram-se num ``SQLModel.metadata`` global compartilhado.
Mudanças de schema vão **exclusivamente** por migrations Alembic (apps/scraper/alembic)
— nunca chame ``SQLModel.metadata.create_all`` fora dos testes.

Não reexportado no ``__init__`` do pacote de propósito: os nomes colidem com os
modelos Pydantic de domínio (``shared_models.models``). Importe de
``shared_models.tables`` explicitamente.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any, Literal, NamedTuple

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlmodel import Field, SQLModel

ListingKind = Literal["aluguel", "venda"]


class Listing(SQLModel, table=True):
    """An OLX listing in the ``listing`` table (read-only pela bot)."""

    __tablename__ = "listing"  # type: ignore
    __table_args__ = (
        CheckConstraint(
            "listing_kind IN ('aluguel', 'venda')",
            name="ck_listing_listing_kind",
        ),
        Index(
            "ix_listing_active_kind_municipality",
            "active",
            "listing_kind",
            "municipality",
        ),
    )

    listing_id: int = Field(primary_key=True)
    active: bool = Field(
        default=True,
        sa_column=Column("active", Boolean, nullable=False, server_default=text("true")),
    )
    listing_kind: ListingKind = Field(
        default="aluguel",
        sa_column=Column(
            "listing_kind",
            Text,
            nullable=False,
            server_default=text("'aluguel'"),
        ),
    )
    url: str
    title: str
    price_value: int | None = None
    old_price: int | None = None
    municipality: str
    neighbourhood: str
    category: str
    images: list[str] = Field(sa_column=Column("images", JSON, nullable=False))
    properties: dict[str, Any] = Field(sa_column=Column("properties", JSON, nullable=False))
    first_seen_at: datetime | None = Field(
        default=None,
        sa_column=Column("first_seen_at", DateTime(timezone=True), server_default=func.now()),
    )
    updated_at: datetime | None = Field(
        default=None,
        sa_column=Column(
            "updated_at",
            DateTime(timezone=True),
            onupdate=lambda: datetime.now(UTC),
        ),
    )


class MarketSnapshot(SQLModel, table=True):
    """Agregado diário dos anúncios ativos. Uma linha por dia UTC.

    ``payload`` é o JSON público do painel (Maceió e Recife). O scraper grava
    no fim da cadeia de coleta; o site só lê.
    """

    __tablename__ = "market_snapshot"  # type: ignore

    collected_on: date = Field(primary_key=True)
    collected_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    payload: dict[str, Any] = Field(sa_column=Column(JSON, nullable=False))


class User(SQLModel, table=True):
    """User identified by Telegram chat_id (dona: bot).

    ``chat_id`` is BIGINT — Telegram user ids can exceed PostgreSQL INTEGER
    (2^31-1).

    Billing (Radar Pro via Telegram Stars): ``plan`` + ``pro_until`` drive
    entitlement; Stars charge/subscription fields mirror Telegram state.
    Email trial: ``email`` + ``email_pro_trial_claimed_at`` for one-time
    free Pro month while Stars checkout is paused.
    """

    __tablename__ = "users"  # type: ignore
    __table_args__ = (
        CheckConstraint(
            "plan IN ('free', 'pro')",
            name="ck_users_plan",
        ),
        UniqueConstraint("email", name="uq_users_email"),
    )

    chat_id: int = Field(
        sa_column=Column("chat_id", BigInteger, primary_key=True, nullable=False)
    )
    created_at: datetime | None = Field(
        default=None,
        sa_column=Column("created_at", DateTime(timezone=True), server_default=func.now()),
    )
    plan: str = Field(
        default="free",
        sa_column=Column(
            "plan",
            Text,
            nullable=False,
            server_default=text("'free'"),
        ),
    )
    pro_until: datetime | None = Field(
        default=None,
        sa_column=Column("pro_until", DateTime(timezone=True), nullable=True),
    )
    stars_telegram_payment_charge_id: str | None = Field(
        default=None,
        sa_column=Column("stars_telegram_payment_charge_id", Text, nullable=True),
    )
    stars_subscription_active: bool = Field(
        default=False,
        sa_column=Column(
            "stars_subscription_active",
            Boolean,
            nullable=False,
            server_default=text("false"),
        ),
    )
    email: str | None = Field(
        default=None,
        sa_column=Column("email", Text, nullable=True),
    )
    email_pro_trial_claimed_at: datetime | None = Field(
        default=None,
        sa_column=Column(
            "email_pro_trial_claimed_at",
            DateTime(timezone=True),
            nullable=True,
        ),
    )


class Alert(SQLModel, table=True):
    """Registered alert. ``neighbourhoods`` is JSON serialized (dona: bot)."""

    __tablename__ = "alerts"  # type: ignore
    __table_args__ = (
        CheckConstraint(
            "min_price IS NOT NULL OR max_price IS NOT NULL",
            name="ck_alert_price_range",
        ),
        CheckConstraint(
            "listing_kind IN ('aluguel', 'venda')",
            name="ck_alert_listing_kind",
        ),
        CheckConstraint(
            "municipality IN ('Maceió', 'Recife')",
            name="ck_alert_municipality",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    chat_id: int = Field(
        sa_column=Column("chat_id", BigInteger, ForeignKey("users.chat_id"), nullable=False)
    )
    alert_name: str | None = Field(default=None, sa_column=Column("alert_name", Text))
    listing_kind: ListingKind = Field(
        default="aluguel",
        sa_column=Column(
            "listing_kind",
            Text,
            nullable=False,
            server_default=text("'aluguel'"),
        ),
    )
    municipality: str = Field(
        default="Maceió",
        sa_column=Column(
            "municipality",
            Text,
            nullable=False,
            server_default=text("'Maceió'"),
        ),
    )
    min_price: int | None = None
    max_price: int | None = None
    min_rooms: int | None = None
    neighbourhoods: list[str] | None = Field(default=None, sa_column=Column("neighbourhoods", JSON))
    categories: list[str] | None = Field(default=None, sa_column=Column("categories", JSON))
    active: bool = Field(
        default=True,
        sa_column=Column("active", Boolean, nullable=False, server_default=text("true")),
    )
    created_at: datetime | None = Field(
        default=None,
        sa_column=Column("created_at", DateTime(timezone=True), server_default=func.now()),
    )


class AlertMatch(SQLModel, table=True):
    """Record that a listing has already been notified for an alert (dona: bot)."""

    __tablename__ = "alert_matches"  # type: ignore

    alert_id: int = Field(
        foreign_key="alerts.id",
        primary_key=True,
    )
    listing_id: int = Field(
        foreign_key="listing.listing_id",
        primary_key=True,
    )
    notified_at: datetime | None = Field(
        default=None,
        sa_column=Column("notified_at", DateTime(timezone=True), server_default=func.now()),
    )


class WatchedListing(SQLModel, table=True):
    """User subscription to a specific listing (dona: bot).

    Baselines (``last_known_price`` / ``last_known_active``) are set on create
    from the current listing row so the first notify only fires on a later change.
    """

    __tablename__ = "watched_listings"  # type: ignore
    __table_args__ = (
        UniqueConstraint(
            "chat_id",
            "listing_id",
            name="uq_watched_listings_chat_listing",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    chat_id: int = Field(
        sa_column=Column("chat_id", BigInteger, ForeignKey("users.chat_id"), nullable=False)
    )
    listing_id: int = Field(foreign_key="listing.listing_id")
    last_known_price: int | None = None
    last_known_active: bool = Field(
        default=True,
        sa_column=Column(
            "last_known_active",
            Boolean,
            nullable=False,
            server_default=text("true"),
        ),
    )
    created_at: datetime | None = Field(
        default=None,
        sa_column=Column("created_at", DateTime(timezone=True), server_default=func.now()),
    )


class ListingAlertMatch(NamedTuple):
    """A listing plus the alert it matched."""

    listing: Listing
    alert_id: int


class WatchedListingChange(NamedTuple):
    """A watched row plus its current listing (used for price/active diffs)."""

    watch: WatchedListing
    listing: Listing
