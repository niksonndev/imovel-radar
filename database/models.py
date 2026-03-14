"""
MODELOS = definição das TABELAS do banco (ORM SQLAlchemy).

Em vez de escrever SQL na mão, cada class abaixo vira uma tabela.
Mapped[int] = coluna inteira; relationship = ligar tabelas (user tem muitos alerts).
"""
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


# Classe base que o SQLAlchemy usa para saber o que criar no banco
class Base(DeclarativeBase):
    pass


# Um registro por pessoa que usou o bot no Telegram
class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(Integer, unique=True, index=True, nullable=False)
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # cascade delete = se apagar o user, apaga alertas e watchlist dele
    alerts: Mapped[list["Alert"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    watched: Mapped[list["WatchedListing"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


# Um "alerta" = busca salva (filtros em JSON) que o job periódico consulta no OLX
class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    filters: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)  # tipo, preço, bairros...
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_checked: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped["User"] = relationship(back_populates="alerts")
    seen: Mapped[list["SeenListing"]] = relationship(
        back_populates="alert", cascade="all, delete-orphan"
    )


# Para cada alerta: quais IDs de anúncio OLX já vimos (para saber o que é "novo")
class SeenListing(Base):
    __tablename__ = "seen_listings"
    __table_args__ = (UniqueConstraint("alert_id", "olx_id", name="uq_alert_olx"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    alert_id: Mapped[int] = mapped_column(ForeignKey("alerts.id", ondelete="CASCADE"), nullable=False)
    olx_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    first_seen: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_seen: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    alert: Mapped["Alert"] = relationship(back_populates="seen")


# Link que o usuário pediu para "observar" preço (/observar)
class WatchedListing(Base):
    __tablename__ = "watched_listings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    olx_id: Mapped[str] = mapped_column(String(64), nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    initial_price: Mapped[float | None] = mapped_column(nullable=True)
    current_price: Mapped[float | None] = mapped_column(nullable=True)
    last_checked: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    price_history: Mapped[list] = mapped_column(JSON, default=list)
    removed_notified: Mapped[bool] = mapped_column(Boolean, default=False)  # já avisamos que sumiu?

    user: Mapped["User"] = relationship(back_populates="watched")
