from __future__ import annotations
from typing import TypedDict
from dataclasses import dataclass
from telegram.ext import CallbackContext, ExtBot


class Listing(TypedDict):
    listId: int
    url: str
    title: str
    priceValue: int | None
    oldPrice: int | None
    municipality: str
    neighbourhood: str | None
    category: str
    images: str  # JSON serializado
    properties: str


class Properties(TypedDict, total=False):
    category: str
    real_estate_type: str  # Aluguel/Venda
    size: int
    rooms: int
    bathrooms: int
    garage_spaces: int
    condominio: int
    iptu: int
    re_features: str
    re_complex_features: str
    re_types: str


@dataclass
class HydratedListing:
    listId: int
    url: str
    title: str
    priceValue: int | None
    oldPrice: int | None
    municipality: str
    neighbourhood: str | None
    category: str
    images: list[str]  # after json.loads
    properties: list[Properties]  # after json.loads


class CreateAlertDraft(TypedDict, total=False):
    """Estado parcial durante o fluxo incremental de criação de alerta."""

    alert_name: str
    min_price: int
    max_price: int
    neighbourhoods: list[str]


class CreateAlertData(TypedDict):
    """Alerta completo, pronto para INSERT. Todos os campos são obrigatórios."""

    user_id: int
    alert_name: str
    min_price: int
    max_price: int
    neighbourhoods: list[str]


class UserData(TypedDict, total=False):
    create_alert_draft: CreateAlertDraft


CustomContext = CallbackContext[ExtBot, UserData, dict, dict]


class Alert(TypedDict):
    id: int
    user_id: int
    alert_name: str
    min_price: int
    max_price: int
    neighbourhoods: str  # JSON array, deserializar quando usar
    active: bool
    created_at: str


class AlertWithChat(Alert):
    chat_id: int  # de users.chat_id
