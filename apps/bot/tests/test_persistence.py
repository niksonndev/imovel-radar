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


class FakePaginator:
    def __init__(self, table: FakeTable) -> None:
        self._table = table

    def paginate(self, **kwargs):
        filter_expr = kwargs.get("FilterExpression")
        names = kwargs.get("ExpressionAttributeNames") or {}
        values = kwargs.get("ExpressionAttributeValues") or {}
        # Exige o alias — o bug de produção era ``store`` sem ExpressionAttributeNames.
        assert filter_expr == "#store = :s", filter_expr
        assert names.get("#store") == "store", names
        expected = values[":s"]
        items = [
            dict(item)
            for (_chat_id, store), item in self._table.items.items()
            if store == expected
        ]
        yield {"Items": items}


class FakeClient:
    def __init__(self, table: FakeTable) -> None:
        self._table = table

    def get_paginator(self, name: str) -> FakePaginator:
        assert name == "scan"
        return FakePaginator(self._table)


class FakeMeta:
    def __init__(self, table: FakeTable) -> None:
        self.client = FakeClient(table)


class FakeTable:
    """Tabela DynamoDB mínima em memória para OCC + get/put/scan."""

    def __init__(self) -> None:
        self.items: dict[tuple[int, str], dict] = {}
        self.meta = FakeMeta(self)

    def get_item(self, Key: dict) -> dict:
        item = self.items.get((Key["chat_id"], Key["store"]))
        return {"Item": dict(item)} if item is not None else {}

    def put_item(
        self,
        Item: dict,
        ConditionExpression: str,
        ExpressionAttributeValues=None,
        ExpressionAttributeNames=None,
    ) -> None:
        names = ExpressionAttributeNames or {}
        assert names.get("#version") == "version", names
        key = (Item["chat_id"], Item["store"])
        existing = self.items.get(key)
        if ConditionExpression == "attribute_not_exists(#version)":
            if existing is not None:
                raise ClientError(
                    {"Error": {"Code": "ConditionalCheckFailedException", "Message": "exists"}},
                    "PutItem",
                )
        elif ConditionExpression == "#version = :expected":
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


def test_get_user_data_scans_with_store_alias() -> None:
    table = FakeTable()
    pers = DynamoDBPersistence(table=table)
    _run(pers.update_user_data(7, {"a": 1}))
    _run(pers.update_chat_data(7, {"ignored": True}))

    loaded = _run(pers.get_user_data())
    assert loaded == {7: {"a": 1}}


def test_get_chat_data_scans_with_store_alias() -> None:
    table = FakeTable()
    pers = DynamoDBPersistence(table=table)
    _run(pers.update_chat_data(9, {"b": 2}))
    _run(pers.update_user_data(9, {"ignored": True}))

    loaded = _run(pers.get_chat_data())
    assert loaded == {9: {"b": 2}}
