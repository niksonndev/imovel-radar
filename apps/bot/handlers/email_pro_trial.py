"""Trial Radar Pro: cadastro de e-mail → 1 mês grátis."""

from __future__ import annotations

import logging

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    filters,
)

from handlers.data import claim_email_pro_trial, user_is_pro
from handlers.ui import keyboards, menus
from models import CustomContext

logger = logging.getLogger(__name__)

ASK_EMAIL = 0


async def email_pro_trial_entry(update: Update, context: CustomContext) -> int:
    query = update.callback_query
    if query is None:
        return ConversationHandler.END
    user = update.effective_user
    if user is None:
        return ConversationHandler.END

    await query.answer()

    try:
        if await user_is_pro(user.id):
            await query.edit_message_text(
                menus.pro_already_active(),
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=keyboards.main_menu_keyboard(),
            )
            return ConversationHandler.END
    except Exception:
        logger.exception("Falha ao checar Pro antes do trial de e-mail user=%s", user.id)

    await query.edit_message_text(
        menus.email_pro_trial_ask(),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=keyboards.email_pro_trial_cancel_keyboard(),
    )
    return ASK_EMAIL


async def email_pro_trial_text(update: Update, context: CustomContext) -> int:
    del context  # unused
    message = update.effective_message
    user = update.effective_user
    if message is None or user is None or not message.text:
        return ASK_EMAIL

    try:
        status, db_user = await claim_email_pro_trial(user.id, message.text)
    except Exception:
        logger.exception("Falha ao reivindicar trial de e-mail user=%s", user.id)
        await message.reply_text(
            menus.email_pro_trial_error(),
            reply_markup=keyboards.main_menu_keyboard(),
        )
        return ConversationHandler.END

    if status == "invalid_email":
        await message.reply_text(
            menus.email_pro_trial_invalid(),
            parse_mode=ParseMode.MARKDOWN,
        )
        return ASK_EMAIL

    if status == "email_taken":
        await message.reply_text(
            menus.email_pro_trial_email_taken(),
            parse_mode=ParseMode.MARKDOWN,
        )
        return ASK_EMAIL

    if status == "already_pro":
        await message.reply_text(
            menus.pro_already_active(),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboards.main_menu_keyboard(),
        )
        return ConversationHandler.END

    if status == "already_claimed":
        await message.reply_text(
            menus.email_pro_trial_already_claimed(),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboards.main_menu_keyboard(),
        )
        return ConversationHandler.END

    await message.reply_text(
        menus.email_pro_trial_activated(pro_until=db_user.pro_until if db_user else None),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=keyboards.main_menu_keyboard(),
    )
    return ConversationHandler.END


async def email_pro_trial_cancel_cb(update: Update, context: CustomContext) -> int:
    del context  # unused
    query = update.callback_query
    if query is None:
        return ConversationHandler.END
    await query.answer()
    await query.edit_message_text(
        menus.email_pro_trial_canceled(),
        reply_markup=keyboards.main_menu_keyboard(),
    )
    return ConversationHandler.END


async def email_pro_trial_cancel_cmd(update: Update, context: CustomContext) -> int:
    del context  # unused
    message = update.effective_message
    if message is not None:
        await message.reply_text(
            menus.email_pro_trial_canceled(),
            reply_markup=keyboards.main_menu_keyboard(),
        )
    return ConversationHandler.END


async def email_pro_trial_start_fallback(update: Update, context: CustomContext) -> int:
    del context  # unused
    message = update.effective_message
    if message is not None:
        await message.reply_text(
            menus.start_welcome(),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboards.main_menu_keyboard(),
        )
    return ConversationHandler.END


def email_pro_trial_conversation() -> ConversationHandler:
    return ConversationHandler(
        name="email_pro_trial",
        persistent=True,
        allow_reentry=True,
        entry_points=[
            CallbackQueryHandler(email_pro_trial_entry, pattern=r"^email_pro_trial$"),
        ],
        states={
            ASK_EMAIL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, email_pro_trial_text),
                CallbackQueryHandler(
                    email_pro_trial_cancel_cb, pattern=r"^email_pro_trial_cancel$"
                ),
            ],
        },
        fallbacks=[
            CommandHandler("cancelar", email_pro_trial_cancel_cmd),
            CommandHandler("start", email_pro_trial_start_fallback),
        ],
    )
