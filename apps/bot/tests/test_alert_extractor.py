import asyncio

import httpx
import pytest

from infrastructure.ai.alert_extractor import (
    extract_alert_intent,
    extract_alert_with_openai,
    match_neighbourhoods,
)


def test_mock_extract_maceio_sale_apartment() -> None:
    res = asyncio.run(
        extract_alert_intent(
            "Apartamento até 400 mil perto da Ponta Verde", provider="mock"
        )
    )
    assert res is not None
    assert res.municipality == "Maceió"
    assert res.listing_kind == "venda"
    assert res.categories == ["Apartamentos"]
    assert res.max_price == 400000
    assert res.min_price is None

    matched = match_neighbourhoods(res.neighbourhoods, ["Ponta Verde", "Jatiúca", "Pajuçara"])
    assert matched == ["Ponta Verde"]


def test_mock_extract_recife_rent_kitnet() -> None:
    res = asyncio.run(
        extract_alert_intent("aluguel kitnet Boa Viagem até 2.500", provider="mock")
    )
    assert res is not None
    assert res.municipality == "Recife"
    assert res.listing_kind == "aluguel"
    assert res.categories == ["Apartamentos"]
    assert res.max_price == 2500

    matched = match_neighbourhoods(res.neighbourhoods, ["Boa Viagem", "Pina"])
    assert matched == ["Boa Viagem"]


def test_mock_extract_natal_sale_house() -> None:
    res = asyncio.run(
        extract_alert_intent(
            "casa em Natal até 500 mil com 3 quartos", provider="mock"
        )
    )
    assert res is not None
    assert res.municipality == "Natal"
    assert res.listing_kind == "venda"
    assert res.categories == ["Casas"]
    assert res.max_price == 500000
    assert res.min_rooms == 3


def test_match_neighbourhoods_synonyms_and_fuzzy() -> None:
    available = ["Ponta Verde", "Jatiúca", "Boa Viagem", "Ponta Negra"]

    # Sinônimos curtos
    assert match_neighbourhoods(["PV"], available) == ["Ponta Verde"]
    assert match_neighbourhoods(["BV"], available) == ["Boa Viagem"]

    # Sem acento / maiúsculas
    assert match_neighbourhoods(["jatiuca"], available) == ["Jatiúca"]
    assert match_neighbourhoods(["ponta negra"], available) == ["Ponta Negra"]

    # Inexistente e casos vazios
    assert match_neighbourhoods(["Bairro Fantasma"], available) == []
    assert match_neighbourhoods([], available) == []
    assert match_neighbourhoods(None, available) == []
    assert match_neighbourhoods(["PV"], []) == []


def test_extract_alert_intent_empty_text() -> None:
    assert asyncio.run(extract_alert_intent("", provider="mock")) is None
    assert asyncio.run(extract_alert_intent("   ", provider="mock")) is None


def test_extract_alert_with_openai_mock_response(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_json_content = (
        '{"municipality": "Maceió", "listing_kind": "aluguel", "categories": ["Apartamentos"], '
        '"min_price": null, "max_price": 3000, "min_rooms": 2, "neighbourhoods": ["Pajuçara"]}'
    )

    def mock_handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Bearer fake-key"
        data = {
            "choices": [
                {
                    "message": {
                        "content": fake_json_content,
                    }
                }
            ]
        }
        return httpx.Response(200, json=data)

    transport = httpx.MockTransport(mock_handler)
    real_async_client = httpx.AsyncClient

    def custom_async_client(*args, **kwargs):
        kwargs["transport"] = transport
        return real_async_client(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", custom_async_client)

    result = asyncio.run(extract_alert_with_openai("texto de teste", api_key="fake-key"))
    assert result is not None
    assert result.municipality == "Maceió"
    assert result.listing_kind == "aluguel"
    assert result.categories == ["Apartamentos"]
    assert result.max_price == 3000
    assert result.min_rooms == 2
    assert result.neighbourhoods == ["Pajuçara"]


def test_extract_alert_with_openai_error_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    def mock_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="Internal Server Error")

    transport = httpx.MockTransport(mock_handler)
    real_async_client = httpx.AsyncClient

    def custom_async_client(*args, **kwargs):
        kwargs["transport"] = transport
        return real_async_client(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", custom_async_client)

    result = asyncio.run(extract_alert_with_openai("texto de teste", api_key="fake-key"))
    assert result is None
