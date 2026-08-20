"""Persistência de estado de conversa da Bot Lambda em DynamoDB (ADR 0006).

Implementa :class:`telegram.ext.BasePersistence` sobre a tabela
``conversation-state`` (PK ``chat_id`` + SK ``store``, TTL nativo).

Layout dos itens:
  * ``user_data``      -> um item por usuário (PK=user_id, SK="user_data"), com
                          TTL expirando drafts de wizard abandonados (ADR 0006).
  * ``chat_data``      -> um item por chat (PK=chat_id, SK="chat_data"), com TTL.
  * ``bot_data``       -> um item global (PK=0, SK="bot_data") — carrossel etc.
  * ``conversations``  -> um item global (PK=0, SK="conversations").
  * ``callback_data``  -> não usado (store_data.callback_data=False).

Cada item trai ``version`` para optimistic concurrency (ConditionExpression no
put, com retry em conflito — correto sob webhooks paralelos/fora de ordem).
"""

from __future__ import annotations

import json
import logging
import threading
import time
from typing import Any, cast

import boto3
from botocore.exceptions import ClientError
from telegram.ext import BasePersistence, PersistenceInput
from telegram.ext._utils.types import CDCData, ConversationDict, ConversationKey

import config

logger = logging.getLogger(__name__)

_GLOBAL_CHAT_ID = 0  # partição sentinela p/ stores globais (bot_data/conversations)
_MAX_RETRIES = 3


def _encode(data: object) -> str:
    return json.dumps(data, ensure_ascii=False, default=str)


def _decode(raw: str | None) -> Any:
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        logger.exception("Falha ao decodificar item persistido; assumindo vazio")
        return {}

class DynamoDBPersistence(BasePersistence[dict[Any, Any], dict[Any, Any], dict[Any, Any]]):
    """Persiste user_data/chat_data/bot_data/conversations em DynamoDB."""

    def __init__(self, table_name: str | None = None, ttl_hours: int | None = None) -> None:
        super().__init__(
            store_data=PersistenceInput(
                user_data=True,
                chat_data=True,
                bot_data=True,
                callback_data=False,
            )
        )
        self._table_name = table_name or config.DYNAMODB_TABLE
        self._ttl_hours = ttl_hours if ttl_hours is not None else config.DYNAMODB_TTL_HOURS
        self._table = boto3.resource("dynamodb").Table(self._table_name)
        self._lock = threading.Lock()

    def _ttl(self) -> int:
        return int(time.time()) + int(self._ttl_hours * 3600)

    # ── helpers ─────────────────────────────────────────────────────────────
    def _get(self, chat_id: int, store: str) -> dict[str, Any]:
        resp = self._table.get_item(Key={"chat_id": chat_id, "store": store})
        return cast(dict[str, Any], resp.get("Item", {}) or {})

    def _put_conditional(
        self, chat_id: int, store: str, data: object, *, version: int | None
    ) -> None:
        """Put com optimistic concurrency.

        Com ``version=None`` exige a inexistência do item (primeira escrita);
        com ``version`` exige que o item tenha exatamente essa versão. Em
        conflito relê o valor atual e tenta de novo (a escrita do chamador é o
        estado completo mais recente — vence).
        """
        for _ in range(_MAX_RETRIES):
            if version is None:
                condition = "attribute_not_exists(version)"
                expr_values: dict[str, Any] = {}
            else:
                condition = "version = :expected"
                expr_values = {":expected": version}

            item: dict[str, Any] = {
                "chat_id": chat_id,
                "store": store,
                "data": _encode(data),
                "version": 1 if version is None else version,
            }
            if store in ("user_data", "chat_data"):
                item["ttl"] = self._ttl()

            try:
                self._table.put_item(
                    Item=item,
                    ConditionExpression=condition,
                    ExpressionAttributeValues=expr_values,
                )
                return
            except ClientError as exc:
                code = getattr(exc, "response", {}).get("Error", {}).get("Code", "")
                if code != "ConditionalCheckFailedException":
                    raise
                current = self._get(chat_id, store)
                if not current:
                    # Item não existe (e.g. expirou via TTL) — tenta criar de novo.
                    version = None
                    continue
                current_version = int(current.get("version", 0))
                if version is not None and current_version == version:
                    # Já está atual — nada a fazer.
                    return
                if version is not None and current_version > version:
                    # Outra invocação gravou já; adotamos vista mais nova.
                    version = current_version
                    continue
                version = current_version + 1
        logger.warning(
            "DynamoDB put: desistiu de gravar %s/%s após %s tentativas",
            chat_id, store, _MAX_RETRIES,
        )

    # ── BasePersistence ─────────────────────────────────────────────────────
    async def get_user_data(self) -> dict[int, dict[Any, Any]]:
        result: dict[int, dict[Any, Any]] = {}
        paginator = self._table.meta.client.get_paginator("scan")
        for page in paginator.paginate(
            TableName=self._table_name,
            FilterExpression="store = :s",
            ExpressionAttributeValues={":s": "user_data"},
        ):
            for item in page.get("Items", []):
                try:
                    result[int(item["chat_id"])] = _decode(item.get("data"))
                except (TypeError, ValueError):
                    continue
        return result

    async def get_chat_data(self) -> dict[int, dict[Any, Any]]:
        result: dict[int, dict[Any, Any]] = {}
        paginator = self._table.meta.client.get_paginator("scan")
        for page in paginator.paginate(
            TableName=self._table_name,
            FilterExpression="store = :s",
            ExpressionAttributeValues={":s": "chat_data"},
        ):
            for item in page.get("Items", []):
                try:
                    result[int(item["chat_id"])] = _decode(item.get("data"))
                except (TypeError, ValueError):
                    continue
        return result

    async def get_bot_data(self) -> dict[Any, Any]:
        item = self._get(_GLOBAL_CHAT_ID, "bot_data")
        return _decode(item.get("data"))

    async def get_callback_data(self) -> CDCData | None:
        return None

    async def get_conversations(self, name: str) -> ConversationDict:
        item = self._get(_GLOBAL_CHAT_ID, "conversations")
        data = _decode(item.get("data"))
        sub = data.get(name, {}) if isinstance(data, dict) else {}
        return cast(ConversationDict, dict(sub))

    async def update_conversation(
        self, name: str, key: ConversationKey, new_state: object | None
    ) -> None:
        with self._lock:
            current = self._get(_GLOBAL_CHAT_ID, "conversations")
            data = _decode(current.get("data"))
            if not isinstance(data, dict):
                data = {}
            block = data.setdefault(name, {})
            if new_state is None:
                block.pop(key, None)
            else:
                block[key] = new_state
            current_version = current.get("version")
            self._put_conditional(
                _GLOBAL_CHAT_ID, "conversations", data,
                version=int(current_version) if current_version is not None else None,
            )

    async def update_user_data(self, user_id: int, data: dict[Any, Any]) -> None:
        with self._lock:
            current = self._get(int(user_id), "user_data")
            current_version = current.get("version")
            self._put_conditional(
                int(user_id), "user_data", data,
                version=int(current_version) if current_version is not None else None,
            )

    async def update_chat_data(self, chat_id: int, data: dict[Any, Any]) -> None:
        with self._lock:
            current = self._get(int(chat_id), "chat_data")
            current_version = current.get("version")
            self._put_conditional(
                int(chat_id), "chat_data", data,
                version=int(current_version) if current_version is not None else None,
            )

    async def update_bot_data(self, data: dict[Any, Any]) -> None:
        with self._lock:
            current = self._get(_GLOBAL_CHAT_ID, "bot_data")
            current_version = current.get("version")
            self._put_conditional(
                _GLOBAL_CHAT_ID, "bot_data", data,
                version=int(current_version) if current_version is not None else None,
            )

    async def update_callback_data(self, data: CDCData) -> None:
        return

    async def drop_chat_data(self, chat_id: int) -> None:
        try:
            self._table.delete_item(Key={"chat_id": int(chat_id), "store": "chat_data"})
        except ClientError:
            logger.exception("drop_chat_data falhou para %s", chat_id)

    async def drop_user_data(self, user_id: int) -> None:
        try:
            self._table.delete_item(Key={"chat_id": int(user_id), "store": "user_data"})
        except ClientError:
            logger.exception("drop_user_data falhou para %s", user_id)

    async def refresh_user_data(self, user_id: int, user_data: dict[Any, Any]) -> None:
        return

    async def refresh_chat_data(self, chat_id: int, chat_data: dict[Any, Any]) -> None:
        return

    async def refresh_bot_data(self, bot_data: dict[Any, Any]) -> None:
        return

    async def flush(self) -> None:
        return

