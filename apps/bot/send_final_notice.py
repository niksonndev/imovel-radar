"""Envio controlado do aviso de encerramento do Telegram."""

from __future__ import annotations

import argparse
import asyncio
import logging

from sqlmodel import Session
from telegram import Bot
from telegram.error import RetryAfter, TelegramError

import config
from database.db import get_engine
from database.queries import get_users_chat_ids
from shutdown_safety import require_remote_database

WHATSAPP_URL = "https://wa.me/5582993345293"

logger = logging.getLogger(__name__)


def announcement_message(site_url: str) -> str:
    updates_url = f"{site_url.rstrip('/')}/novidades"
    return (
        "Olá! Este canal de atendimento pelo Telegram será encerrado.\n\n"
        "Para continuar sua busca por imóveis, fale com o André Assistente "
        f"Imobiliário pelo WhatsApp: {WHATSAPP_URL}\n\n"
        "Alertas e preferências salvos no Telegram não serão transferidos. "
        "Ao iniciar a conversa, conte novamente ao André o que você procura.\n\n"
        f"Acompanhe os próximos comunicados: {updates_url}\n\n"
        "Obrigado por acompanhar o projeto."
    )


def recipient_chat_ids() -> list[int]:
    with Session(get_engine()) as session:
        return get_users_chat_ids(session)


async def send_notice(chat_ids: list[int], message: str) -> tuple[int, int]:
    bot = Bot(token=config.get_bot_token())
    sent = 0
    failed = 0
    try:
        await bot.initialize()
    except TelegramError:
        raise RuntimeError(
            "Telegram Bot API authentication failed; verify the SSM token."
        ) from None
    try:
        for chat_id in chat_ids:
            try:
                await bot.send_message(chat_id=chat_id, text=message, disable_web_page_preview=True)
                sent += 1
            except RetryAfter as error:
                await asyncio.sleep(error.retry_after + 1)
                try:
                    await bot.send_message(
                        chat_id=chat_id,
                        text=message,
                        disable_web_page_preview=True,
                    )
                    sent += 1
                except TelegramError:
                    failed += 1
            except TelegramError:
                failed += 1
            await asyncio.sleep(1)
    finally:
        await bot.shutdown()
    return sent, failed


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--send",
        action="store_true",
        help="Enviar o aviso; sem esta opção, somente exibe a prévia.",
    )
    parser.add_argument(
        "--confirm-count",
        type=int,
        help="Confirma a quantidade exata de destinatários mostrada na prévia.",
    )
    args = parser.parse_args()

    if args.send:
        try:
            require_remote_database(config.DATABASE_URL)
        except ValueError as error:
            parser.error(str(error))

    chat_ids = recipient_chat_ids()
    message = announcement_message(config.PUBLIC_SITE_URL)
    print(f"Destinatários Telegram: {len(chat_ids)}")
    print("Prévia do aviso:\n")
    print(message)

    if not args.send:
        print("\nPrévia apenas; nenhuma mensagem foi enviada.")
        return 0
    if not chat_ids:
        parser.error("nenhum destinatário Telegram encontrado; envio cancelado")
    if args.confirm_count != len(chat_ids):
        parser.error("use --confirm-count com a quantidade exata exibida na prévia")

    sent, failed = await send_notice(chat_ids, message)
    logger.info("Aviso Telegram concluído: enviados=%d falhas=%d", sent, failed)
    return 1 if failed else 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    try:
        raise SystemExit(asyncio.run(main()))
    except RuntimeError:
        logger.error("Telegram Bot API authentication failed; verify the SSM token.")
        raise SystemExit(1) from None
