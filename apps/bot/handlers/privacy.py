"""Comandos de privacidade e exclusão dos dados da conta."""

from __future__ import annotations

import inspect
import logging
import re
import secrets
from collections.abc import Awaitable, Callable
from html import escape
from typing import cast

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import ConversationHandler

import config
from handlers.data import delete_user_data, get_user, mark_pro_subscription_canceled
from models import CustomContext

logger = logging.getLogger(__name__)

_DELETE_CALLBACK = re.compile(r"^privacy_delete_(yes|no)_([a-f0-9]{12})$")


async def privacy_policy_cmd(update: Update, context: CustomContext) -> None:
    del context
    message = update.effective_message
    if message is None:
        return
    await message.reply_text(
        f'<a href="{config.PUBLIC_SITE_URL}/privacidade">Política de Privacidade</a> · '
        f'<a href="{config.PUBLIC_SITE_URL}/termos">Termos de Uso</a>\n'
        "Para apagar seus dados, use /excluir_dados.",
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True,
    )


async def support_cmd(update: Update, context: CustomContext) -> None:
    del context
    message = update.effective_message
    if message is None:
        return
    if config.SUPPORT_URL.startswith(("https://", "http://")):
        target = escape(config.SUPPORT_URL, quote=True)
        text = f'<a href="{target}">Abrir canal de atendimento</a>'
    else:
        text = (
            "O canal de atendimento humano ainda não está configurado. "
            "Não envie dados sensíveis por aqui."
        )
    await message.reply_text(text, parse_mode=ParseMode.HTML, disable_web_page_preview=True)


async def privacy_delete_request(update: Update, context: CustomContext) -> int:
    message = update.effective_message
    if message is None or context.user_data is None:
        return ConversationHandler.END

    context.user_data.pop("create_alert_draft", None)
    context.user_data.pop("create_alert_wizard_state", None)
    context.user_data.pop("assistant_pending_alert", None)
    token = secrets.token_hex(6)
    context.user_data["pending_data_deletion_token"] = token
    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "Excluir meus dados", callback_data=f"privacy_delete_yes_{token}"
                ),
                InlineKeyboardButton("Manter conta", callback_data=f"privacy_delete_no_{token}"),
            ]
        ]
    )
    await message.reply_text(
        "A exclusão remove sua conta, alertas, anúncios acompanhados, e-mail do trial "
        "e memória de conversa. Mensagens já entregues permanecem no seu histórico do Telegram. "
        "Se houver renovação Stars ativa, ela será cancelada antes da exclusão. Confirma?",
        reply_markup=keyboard,
    )
    return ConversationHandler.END


async def privacy_delete_confirm_cb(update: Update, context: CustomContext) -> None:
    query = update.callback_query
    user = update.effective_user
    if query is None or user is None:
        return
    match = _DELETE_CALLBACK.match(query.data or "")
    if match is None:
        return
    action, token = match.groups()
    await query.answer()

    user_data = context.user_data
    if user_data is None or user_data.get("pending_data_deletion_token") != token:
        await query.edit_message_text(
            "Esta confirmação expirou. Use /excluir_dados para começar de novo."
        )
        return
    if action == "no":
        user_data.pop("pending_data_deletion_token", None)
        await query.edit_message_text("Tudo bem. Seus dados foram mantidos.")
        return

    try:
        db_user = await get_user(user.id)
        if db_user is not None and db_user.stars_subscription_active:
            charge_id = db_user.stars_telegram_payment_charge_id
            if not charge_id:
                await query.edit_message_text(
                    "Não consegui validar a renovação Stars. Cancele em "
                    "Configurações do Telegram → Stars → Minhas assinaturas e tente novamente."
                )
                return
            await context.bot.edit_user_star_subscription(
                user_id=user.id,
                telegram_payment_charge_id=charge_id,
                is_canceled=True,
            )
            await mark_pro_subscription_canceled(user.id)
        await delete_user_data(user.id)
    except Exception:
        logger.exception("Falha no fluxo de exclusão de dados")
        await query.edit_message_text(
            "Não consegui concluir a exclusão agora. Seus dados não foram confirmados "
            "como removidos; "
            "tente novamente ou fale com o suporte."
        )
        return

    for key in (
        "pending_data_deletion_token",
        "create_alert_draft",
        "create_alert_wizard_state",
        "assistant_pending_alert",
        "assistant_history",
        "assistant_history_updated_at",
    ):
        user_data.pop(key, None)
    persistence = getattr(context.application, "persistence", None)
    purge = getattr(persistence, "purge_user_records", None)
    try:
        if callable(purge) and inspect.iscoroutinefunction(purge):
            purge_user = cast(Callable[[int], Awaitable[None]], purge)
            await purge_user(user.id)
        else:
            drop_user = getattr(context.application, "drop_user_data", None)
            drop_chat = getattr(context.application, "drop_chat_data", None)
            if callable(drop_user):
                drop_user_data = cast(Callable[[int], Awaitable[None]], drop_user)
                await drop_user_data(user.id)
            if callable(drop_chat):
                drop_chat_data = cast(Callable[[int], Awaitable[None]], drop_chat)
                await drop_chat_data(user.id)
    except Exception:
        logger.exception("Falha ao limpar estado temporário após exclusão")
        await query.edit_message_text(
            "Sua conta e os dados imobiliários foram excluídos. Não consegui confirmar a limpeza "
            "da memória temporária; ela expira automaticamente em até 4 horas."
        )
        return

    await query.edit_message_text(
        "Seus dados do Imóvel Radar foram excluídos e, quando aplicável, a renovação "
        "foi cancelada. "
        "As mensagens já enviadas continuam no histórico do Telegram."
    )
