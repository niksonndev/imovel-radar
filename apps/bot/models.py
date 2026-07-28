from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, TypedDict

from telegram.ext import CallbackContext, ExtBot


class UserData(TypedDict, total=False):
    create_alert_draft: CreateAlertDraft
    create_alert_wizard_state: CreateAlertWizardState


class CustomContext(CallbackContext[ExtBot, UserData, dict, dict]):
    pass


class CreateAlertDraft(TypedDict, total=False):
    """Estado parcial durante o fluxo incremental de criação de alerta."""

    alert_name: str
    min_price: int
    max_price: int
    neighbourhoods: list[str]


class CreateAlertWizardState(TypedDict, total=False):
    """Estado temporário da interface do wizard, fora do draft persistível."""

    awaiting: Literal["price_min", "price_max"]
    neighbourhood_options: list[str]
    neighbourhood_page: int