"""SQLModel models (tables) for the scraper's SQLite database.

Local **persistence** layer. API response classes (`shared_models.api_schemas`)
are the shared contract between services and live in `packages/shared-models`.
"""

from datetime import UTC, datetime
from typing import Any, NamedTuple

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    Text,
    func,
    text,
)
from sqlmodel import Field, SQLModel


class Listing(SQLModel, table=True):
    """An OLX listing persisted in the ``listing`` table."""

    __tablename__ = "listing"  # type: ignore

    listing_id: int = Field(primary_key=True)
    active: bool = Field(
        default=True,
        sa_column=Column("active", Boolean, nullable=False, server_default=text("true")),
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


class User(SQLModel, table=True):
    """User identified by Telegram chat_id."""

    __tablename__ = "users"  # type: ignore

    chat_id: int = Field(primary_key=True)
    created_at: datetime | None = Field(
        default=None,
        sa_column=Column("created_at", DateTime(timezone=True), server_default=func.now()),
    )


class Alert(SQLModel, table=True):
    """Registered alert. ``neighbourhoods`` is JSON serialized."""

    __tablename__ = "alerts"  # type: ignore
    __table_args__ = (
        CheckConstraint(
            "min_price IS NOT NULL OR max_price IS NOT NULL",
            name="ck_alert_price_range",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    chat_id: int = Field(
        sa_column=Column("chat_id", Integer, ForeignKey("users.chat_id"), nullable=False)
    )
    alert_name: str | None = Field(default=None, sa_column=Column("alert_name", Text))
    min_price: int | None = None
    max_price: int | None = None
    neighbourhoods: list[str] | None = Field(default=None, sa_column=Column("neighbourhoods", JSON))
    active: bool = Field(
        default=True,
        sa_column=Column("active", Boolean, nullable=False, server_default=text("true")),
    )
    created_at: datetime | None = Field(
        default=None,
        sa_column=Column("created_at", DateTime(timezone=True), server_default=func.now()),
    )


class AlertMatch(SQLModel, table=True):
    """Record that a listing has already been notified for an alert."""

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

class ListingAlertMatch(NamedTuple):
    listing: Listing
    alert_id: int