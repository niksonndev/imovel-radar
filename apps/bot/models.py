from __future__ import annotations

from typing import Literal, TypedDict

from shared_models.tables import ListingKind
from telegram.ext import CallbackContext, ExtBot


class UserData(TypedDict, total=False):
    create_alert_draft: CreateAlertDraft
    create_alert_wizard_state: CreateAlertWizardState


class CustomContext(CallbackContext[ExtBot, UserData, dict, dict]):
    pass


class CreateAlertDraft(TypedDict, total=False):
    """Estado parcial durante o fluxo incremental de criação de alerta."""

    alert_name: str
    listing_kind: ListingKind
    min_price: int
    max_price: int
    min_rooms: int | None
    categories: list[str]
    neighbourhoods: list[str]
    created_alert_id: int


class CreateAlertWizardState(TypedDict, total=False):
    """Estado temporário da interface do wizard, fora do draft persistível."""

    awaiting: Literal["price_min", "price_max"]
    price_prompt_chat_id: int
    price_prompt_message_id: int
    neighbourhood_options: list[str]
    neighbourhood_page: int
    confirming: bool
    seed_done: bool
    alert_was_created: bool
