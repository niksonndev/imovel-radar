"""Entry point AWS Lambda da Bot Lambda (webhook do Telegram + notificação).

Dois gatilhos possíveis (ADR 0004):
  * API Gateway (webhook) — evento com ``body`` contendo o JSON do Telegram.
    ``Update.de_json`` -> ``Application.process_update`` (sem long-running).
  * EventBridge (notificação horária) — evento com ``source == "aws.events"``;
    re-executa o job de notificação (lê do Postgres, envia carrosséis).

Quente-reuso: a ``Application`` é construída/inicializada uma vez por instância
(module-level) e reciclada entre invocações.
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from pathlib import Path

from telegram import Update
from telegram.ext import Application, ContextTypes

import config
from application import build_application
from jobs.polling_job import notify_new_matches
from models import CustomContext, UserData
from persistence import DynamoDBPersistence

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=getattr(logging, config.LOG_LEVEL, logging.INFO),
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

_application: Application | None = None
_application_lock = asyncio.Lock()


async def _get_application() -> Application:
    """Constrói e inicializa a Application uma vez por instância quente."""
    global _application
    if _application is None:
        async with _application_lock:
            if _application is None:
                app = build_application(
                    persistence=DynamoDBPersistence(),
                    context_types=ContextTypes(context=CustomContext, user_data=UserData),
                )
                await app.initialize()
                _application = app
    return _application


def _is_eventbridge(event: dict) -> bool:
    return event.get("source") == "aws.events" or event.get("detail-type") in (
        "Scheduled Event",
        "Schenduled Event",
    )


async def _handle_webhook(event: dict) -> dict:
    body = event.get("body", "")
    if not body:
        return {"statusCode": 400, "body": json.dumps({"ok": False, "error": "empty body"})}

    app = await _get_application()
    try:
        update = Update.de_json(json.loads(body), app.bot)
    except (TypeError, ValueError, json.JSONDecodeError):
        logger.exception("Falha ao decodificar update do Telegram")
        return {"statusCode": 400, "body": json.dumps({"ok": False, "error": "bad update"})}

    try:
        await app.process_update(update)
        await app.update_persistence()
    except Exception:
        logger.exception("Falha ao processar update")
        return {"statusCode": 200, "body": json.dumps({"ok": True, "handled": False})}

    return {"statusCode": 200, "body": json.dumps({"ok": True, "handled": True})}


async def _handle_notify() -> None:
    app = await _get_application()
    await notify_new_matches(app)
    await app.update_persistence()


def lambda_handler(event: dict | None, context: object | None) -> dict:
    """Handler AWS Lambda — roteia por EventBridge vs. API Gateway."""
    del context
    event = event or {}
    logger.info("Lambda bot invocada (typed=%s)", _is_eventbridge(event))

    if _is_eventbridge(event):
        asyncio.run(_handle_notify())
        return {"statusCode": 200}

    return asyncio.run(_handle_webhook(event))


if __name__ == "__main__":
    # Smoke local: simula um evento EventBridge
    lambda_handler({"source": "aws.events", "detail-type": "Scheduled Event"}, None)
