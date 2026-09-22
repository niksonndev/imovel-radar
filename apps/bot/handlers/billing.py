"""Radar Pro via Telegram Stars (XTR) — invoice, checkout e cancelamento."""

from __future__ import annotations

import logging
import re
from datetime import UTC, datetime, timedelta

from telegram import LabeledPrice, Update
from telegram.constants import ParseMode
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    PreCheckoutQueryHandler,
    filters,
)

import config
from handlers.data import (
    activate_pro,
    get_user,
    mark_pro_subscription_canceled,
    user_is_pro,
)
from handlers.ui import keyboards, menus
from models import CustomContext

logger = logging.getLogger(__name__)

PRO_PAYLOAD_RE = re.compile(r"^pro_monthly:(\d+)$")
PRO_PAYLOAD_PREFIX = "pro_monthly:"


def _pro_invoice_payload(chat_id: int) -> str:
    return f"{PRO_PAYLOAD_PREFIX}{chat_id}"


def _parse_pro_payload(payload: str) -> int | None:
    match = PRO_PAYLOAD_RE.match(payload or "")
    if match is None:
        return None
    return int(match.group(1))


async def pro_subscribe_callback(update: Update, context: CustomContext) -> None:
    query = update.callback_query
    if query is None:
        return
    user = update.effective_user
    if user is None:
        return

    await query.answer()

    try:
        if await user_is_pro(user.id):
            await query.message.reply_text(  # type: ignore[union-attr]
                menus.pro_already_active(),
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=keyboards.main_menu_keyboard(),
            )
            return
    except Exception:
        logger.exception("Falha ao checar Pro para %s", user.id)

    title = "Radar Pro"
    description = (
        f"Até {config.ALERT_PRO_CAP} alertas e {config.WATCHLIST_PRO_CAP} anúncios "
        f"acompanhados. ≈ {config.PRO_PRICE_BRL_LABEL}/mês. Renova a cada 30 dias."
    )
    prices = [LabeledPrice(label="Radar Pro (mensal)", amount=config.PRO_STARS_AMOUNT)]

    try:
        await context.bot.send_invoice(
            chat_id=user.id,
            title=title,
            description=description,
            payload=_pro_invoice_payload(user.id),
            provider_token="",
            currency="XTR",
            prices=prices,
            api_kwargs={
                "subscription_period": config.PRO_SUBSCRIPTION_PERIOD_SECONDS,
            },
        )
    except Exception:
        logger.exception("Falha ao enviar invoice Stars para %s", user.id)
        await query.message.reply_text(  # type: ignore[union-attr]
            "Não consegui abrir o pagamento agora. Tente de novo em instantes.",
            reply_markup=keyboards.main_menu_keyboard(),
        )


async def pro_precheckout(update: Update, context: CustomContext) -> None:
    del context  # unused
    query = update.pre_checkout_query
    if query is None:
        return

    chat_id = _parse_pro_payload(query.invoice_payload)
    if chat_id is None or chat_id != query.from_user.id:
        await query.answer(ok=False, error_message="Pedido inválido.")
        return
    if query.currency != "XTR" or query.total_amount != config.PRO_STARS_AMOUNT:
        await query.answer(ok=False, error_message="Valor incorreto.")
        return
    await query.answer(ok=True)


async def pro_successful_payment(update: Update, context: CustomContext) -> None:
    del context  # unused
    message = update.effective_message
    user = update.effective_user
    if message is None or user is None or message.successful_payment is None:
        return

    payment = message.successful_payment
    chat_id = _parse_pro_payload(payment.invoice_payload)
    if chat_id is None or chat_id != user.id:
        logger.warning(
            "successful_payment payload inválido: %s user=%s",
            payment.invoice_payload,
            user.id,
        )
        return

    pro_until = payment.subscription_expiration_date
    if pro_until is None:
        pro_until = datetime.now(UTC) + timedelta(
            seconds=config.PRO_SUBSCRIPTION_PERIOD_SECONDS
        )
    elif pro_until.tzinfo is None:
        pro_until = pro_until.replace(tzinfo=UTC)

    try:
        await activate_pro(
            chat_id=chat_id,
            pro_until=pro_until,
            telegram_payment_charge_id=payment.telegram_payment_charge_id,
            subscription_active=True,
        )
    except Exception:
        logger.exception("Falha ao ativar Pro após pagamento user=%s", chat_id)
        await message.reply_text(
            "Pagamento recebido, mas falhei ao ativar o Pro. Fale com o suporte.",
            reply_markup=keyboards.main_menu_keyboard(),
        )
        return

    await message.reply_text(
        menus.pro_activated(),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=keyboards.main_menu_keyboard(),
    )


async def cancel_pro_cmd(update: Update, context: CustomContext) -> None:
    assert update.effective_message is not None
    user = update.effective_user
    if user is None:
        return

    try:
        db_user = await get_user(user.id)
    except Exception:
        logger.exception("Falha ao carregar usuário %s para cancelar Pro", user.id)
        await update.effective_message.reply_text(
            "Não consegui cancelar agora. Tente de novo.",
            reply_markup=keyboards.main_menu_keyboard(),
        )
        return

    if db_user is None or not db_user.stars_subscription_active:
        await update.effective_message.reply_text(
            menus.pro_cancel_none(),
            reply_markup=keyboards.main_menu_keyboard(),
        )
        return

    charge_id = db_user.stars_telegram_payment_charge_id
    if not charge_id:
        await update.effective_message.reply_text(
            menus.pro_cancel_none(),
            reply_markup=keyboards.main_menu_keyboard(),
        )
        return

    try:
        await context.bot.edit_user_star_subscription(
            user_id=user.id,
            telegram_payment_charge_id=charge_id,
            is_canceled=True,
        )
        await mark_pro_subscription_canceled(user.id)
    except Exception:
        logger.exception("Falha ao cancelar assinatura Stars user=%s", user.id)
        await update.effective_message.reply_text(
            "Não consegui cancelar no Telegram. "
            "Você também pode cancelar em Configurações → Stars → Minhas assinaturas.",
            reply_markup=keyboards.main_menu_keyboard(),
        )
        return

    await update.effective_message.reply_text(
        menus.pro_cancel_confirm(),
        reply_markup=keyboards.main_menu_keyboard(),
    )


def register_billing_handlers(app) -> None:
    # Stars checkout só quando BILLING_ENABLED; cancelamento fica sempre
    # disponível para assinantes existentes.
    if config.BILLING_ENABLED:
        app.add_handler(
            CallbackQueryHandler(pro_subscribe_callback, pattern=r"^pro_subscribe$")
        )
        app.add_handler(PreCheckoutQueryHandler(pro_precheckout))
        app.add_handler(
            MessageHandler(filters.SUCCESSFUL_PAYMENT, pro_successful_payment),
        )
    app.add_handler(CommandHandler("cancelar_pro", cancel_pro_cmd))
