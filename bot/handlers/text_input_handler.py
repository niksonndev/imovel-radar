"""Entrada de texto livre durante o wizard de novo alerta."""

from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

from bot.novo_alerta_wizard import (
    NEW_ALERT_STEP_KEY,
    WIZ_NAME,
    WIZ_PRICE_MAX,
    WIZ_PRICE_MIN,
    wiz_name,
    wiz_price_max,
    wiz_price_min,
)


async def handle_wizard_text(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Encaminha mensagens de texto para o passo ativo do wizard, se houver."""
    if context.user_data.get(NEW_ALERT_STEP_KEY) is None:
        return

    if update.message is None or not update.message.text:
        return

    step = context.user_data[NEW_ALERT_STEP_KEY]
    if step == WIZ_PRICE_MIN:
        await wiz_price_min(update, context)
    elif step == WIZ_PRICE_MAX:
        await wiz_price_max(update, context)
    elif step == WIZ_NAME:
        await wiz_name(update, context)
