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
            dict(item) for (_chat_id, store), item in self._table.items.items() if store == expected
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

    def update_item(
        self,
        Key: dict,
        UpdateExpression: str,
        ExpressionAttributeNames: dict,
        ExpressionAttributeValues: dict,
        ConditionExpression: str | None = None,
        ReturnValues: str | None = None,
    ) -> dict:
        key = (Key["chat_id"], Key["store"])
        item = self.items.setdefault(key, {"chat_id": Key["chat_id"], "store": Key["store"]})
        if ConditionExpression:
            message_count = item.get("messages", 0)
            if message_count >= ExpressionAttributeValues[":message_limit"]:
                raise ClientError(
                    {"Error": {"Code": "ConditionalCheckFailedException"}}, "UpdateItem"
                )
            if (
                ":audio_limit" in ExpressionAttributeValues
                and item.get("audio", 0) >= ExpressionAttributeValues[":audio_limit"]
            ):
                raise ClientError(
                    {"Error": {"Code": "ConditionalCheckFailedException"}}, "UpdateItem"
                )
        item["ttl"] = ExpressionAttributeValues[":expires"]
        add_expression = UpdateExpression.split("ADD ", 1)[1]
        for fragment in add_expression.split(","):
            name_alias, value_alias = fragment.strip().split()
            name = ExpressionAttributeNames[name_alias]
            item[name] = item.get(name, 0) + ExpressionAttributeValues[value_alias]
        return {"Attributes": dict(item) if ReturnValues else {}}


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
    assert "ttl" in table.items[(0, "conversations")]


def test_user_data_has_ttl_bot_data_does_not() -> None:
    table = FakeTable()
    pers = DynamoDBPersistence(table=table)
    _run(pers.update_user_data(1, {"a": 1}))
    _run(pers.update_bot_data({"leftover": True}))

    assert "ttl" in table.items[(1, "user_data")]
    assert "ttl" not in table.items[(0, "bot_data")]


def test_chat_data_uses_carousel_ttl() -> None:
    table = FakeTable()
    pers = DynamoDBPersistence(table=table, ttl_hours=4, carousel_ttl_hours=168)
    _run(pers.update_user_data(1, {"a": 1}))
    _run(pers.update_chat_data(1, {"carousel_1": {"cards": []}}))
    user_ttl = table.items[(1, "user_data")]["ttl"]
    chat_ttl = table.items[(1, "chat_data")]["ttl"]
    assert abs((chat_ttl - user_ttl) - (168 - 4) * 3600) <= 1


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


def test_daily_assistant_usage_is_capped_and_expires() -> None:
    table = FakeTable()
    persistence = DynamoDBPersistence(table=table)

    assert _run(
        persistence.consume_daily_assistant_usage(
            42, audio=True, message_limit=2, audio_limit=1, audio_seconds=30
        )
    )
    assert not _run(
        persistence.consume_daily_assistant_usage(
            42, audio=True, message_limit=2, audio_limit=1, audio_seconds=10
        )
    )
    assert _run(
        persistence.consume_daily_assistant_usage(42, audio=False, message_limit=2, audio_limit=1)
    )
    assert not _run(
        persistence.consume_daily_assistant_usage(42, audio=False, message_limit=2, audio_limit=1)
    )

    item = next(item for item in table.items.values() if item["chat_id"] == 42)
    assert item["messages"] == 2
    assert item["audio"] == 1
    assert item["audio_seconds"] == 30
    assert "ttl" in item


def test_daily_assistant_tokens_are_aggregated() -> None:
    table = FakeTable()
    persistence = DynamoDBPersistence(table=table)

    _run(persistence.record_daily_assistant_tokens(42, 10))
    _run(persistence.record_daily_assistant_tokens(42, 15, input_tokens=11, output_tokens=4))

    item = next(item for item in table.items.values() if item["chat_id"] == 42)
    assert item["tokens"] == 25
    assert item["input_tokens"] == 11
    assert item["output_tokens"] == 4
    assert "ttl" in item


def test_purge_user_records_clears_only_matching_user() -> None:
    table = FakeTable()
    persistence = DynamoDBPersistence(table=table)
    _run(persistence.update_user_data(42, {"assistant_history": ["private"]}))
    _run(persistence.update_chat_data(42, {"carousel": "state"}))
    _run(persistence.consume_daily_assistant_usage(42, audio=False, message_limit=5, audio_limit=1))
    _run(persistence.update_conversation("new_alert", (42, 42), 2))
    _run(persistence.update_conversation("new_alert", (43, 43), 2))

    _run(persistence.purge_user_records(42))

    assert not any(chat_id == 42 for chat_id, _store in table.items)
    stored = json.loads(table.items[(0, "conversations")]["data"])
    assert encode_conversation_key((42, 42)) not in stored["new_alert"]
    assert stored["new_alert"][encode_conversation_key((43, 43))] == 2
