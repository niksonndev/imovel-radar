from __future__ import annotations

import asyncio
import json

from botocore.exceptions import ClientError

from persistence import (
    DynamoDBPersistence,
    decode_conversation_block,
    decode_conversation_key,
    encode_conversation_key,
)


class FakeTable:
    """Tabela DynamoDB mínima em memória para OCC + get/put."""

    def __init__(self) -> None:
        self.items: dict[tuple[int, str], dict] = {}

    def get_item(self, Key: dict) -> dict:
        item = self.items.get((Key["chat_id"], Key["store"]))
        return {"Item": dict(item)} if item is not None else {}

    def put_item(
        self, Item: dict, ConditionExpression: str, ExpressionAttributeValues=None
    ) -> None:
        key = (Item["chat_id"], Item["store"])
        existing = self.items.get(key)
        if ConditionExpression == "attribute_not_exists(version)":
            if existing is not None:
                raise ClientError(
                    {"Error": {"Code": "ConditionalCheckFailedException", "Message": "exists"}},
                    "PutItem",
                )
        elif ConditionExpression == "version = :expected":
            expected = (ExpressionAttributeValues or {}).get(":expected")
            if existing is None or existing.get("version") != expected:
                raise ClientError(
                    {"Error": {"Code": "ConditionalCheckFailedException", "Message": "version"}},
                    "PutItem",
                )
        else:
            raise AssertionError(f"condição inesperada: {ConditionExpression}")
        self.items[key] = dict(Item)

    def delete_item(self, Key: dict) -> None:
        self.items.pop((Key["chat_id"], Key["store"]), None)


def _run(coro):
    return asyncio.run(coro)


def test_conversation_key_roundtrip() -> None:
    key = (123456, 123456)
    encoded = encode_conversation_key(key)
    json.loads(encoded)  # deve ser JSON válido (lista)
    assert decode_conversation_key(encoded) == key


def test_decode_conversation_block_restores_tuple_keys() -> None:
    key = (1, 2)
    block = {encode_conversation_key(key): 3}
    decoded = decode_conversation_block(block)
    assert decoded[key] == 3


def test_put_increments_version() -> None:
    table = FakeTable()
    pers = DynamoDBPersistence(table=table)

    _run(pers.update_user_data(10, {"draft": 1}))
    item = table.items[(10, "user_data")]
    assert item["version"] == 1
    assert json.loads(item["data"]) == {"draft": 1}

    _run(pers.update_user_data(10, {"draft": 2}))
    item = table.items[(10, "user_data")]
    assert item["version"] == 2
    assert json.loads(item["data"]) == {"draft": 2}


def test_put_retries_on_stale_version() -> None:
    table = FakeTable()
    pers = DynamoDBPersistence(table=table)
    _run(pers.update_user_data(10, {"n": 1}))
    table.items[(10, "user_data")]["version"] = 5

    pers._put_conditional(10, "user_data", {"n": 9}, version=1)
    item = table.items[(10, "user_data")]
    assert item["version"] == 6
    assert json.loads(item["data"]) == {"n": 9}


def test_update_conversation_encodes_tuple_keys() -> None:
    table = FakeTable()
    pers = DynamoDBPersistence(table=table)
    key = (4242, 4242)
    _run(pers.update_conversation("new_alert", key, 2))

    stored = json.loads(table.items[(0, "conversations")]["data"])
    assert encode_conversation_key(key) in stored["new_alert"]
    assert stored["new_alert"][encode_conversation_key(key)] == 2

    loaded = _run(pers.get_conversations("new_alert"))
    assert loaded[key] == 2
    assert table.items[(0, "conversations")]["version"] == 1
