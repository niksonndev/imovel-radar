from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, TypedDict

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


@dataclass
class CreateAlertData:
    """Alerta completo, pronto para INSERT. Todos os campos são obrigatórios."""

    user_id: int
    alert_name: str
    min_price: int
    max_price: int
    neighbourhoods: list[str]


class CreateAlertWizardState(TypedDict, total=False):
    """Estado temporário da interface do wizard, fora do draft persistível."""

    awaiting: Literal["price_min", "price_max"]
    neighbourhood_options: list[str]
    neighbourhood_page: int


class UserData(TypedDict, total=False):
    create_alert_draft: CreateAlertDraft
    create_alert_wizard_state: CreateAlertWizardState


class CustomContext(CallbackContext[ExtBot, UserData, dict, dict]):
    pass


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
