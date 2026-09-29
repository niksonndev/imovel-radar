import asyncio

import httpx
import pytest

from infrastructure.ai.assistant_intent import (
    extract_assistant_intent,
    extract_assistant_intent_with_openai,
    mock_extract_assistant_intent,
)


def test_mock_remover_alertas_with_ref() -> None:
    intent = mock_extract_assistant_intent("remove o alerta de ponta verde")
    assert intent.tool == "remover_alertas"
    assert intent.alert_ref and "ponta verde" in intent.alert_ref.lower()


def test_mock_registra_nova_ref_apos_apagar() -> None:
    intent = mock_extract_assistant_intent("quero apagar o alerta da jatiuca")
    assert intent.tool == "remover_alertas"
    assert intent.alert_ref and "jatiuca" in intent.alert_ref.lower()


def test_mock_listar_alertas() -> None:
    intent = mock_extract_assistant_intent("quais são meus alertas")
    assert intent.tool == "listar_alertas"


def test_mock_consultar_mercado() -> None:
    intent = mock_extract_assistant_intent("média de aluguel em maceió")
    assert intent.tool == "consultar_mercado"
    assert intent.municipality == "Maceió"
    assert intent.listing_kind == "aluguel"


def test_mock_criar_alerta() -> None:
    intent = mock_extract_assistant_intent("quero um apartamento em ponta verde até 2000")
    assert intent.tool == "criar_alerta"


def test_mock_ajuda_e_nada() -> None:
    assert mock_extract_assistant_intent("o que você faz?").tool == "ajuda"
    assert mock_extract_assistant_intent("tudo bem?").tool == "nada"
    assert mock_extract_assistant_intent("").tool == "nada"


def test_extract_assistant_intent_vazio() -> None:
    assert asyncio.run(extract_assistant_intent("", provider="mock")).tool == "nada"


def test_extract_openai_path(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_json = (
        '{"tool": "remover_alertas", "alert_ref": "ponta verde", '
        '"municipality": null, "listing_kind": null, "neighbourhoods": null}'
    )

    def mock_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": fake_json}}]},
            request=request,
        )

    transport = httpx.MockTransport(mock_handler)
    real_async_client = httpx.AsyncClient

    def custom_async_client(*args, **kwargs):
        kwargs["transport"] = transport
        return real_async_client(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", custom_async_client)

    result = asyncio.run(extract_assistant_intent("texto", provider="openai", api_key="k"))
    assert result.tool == "remover_alertas"
    assert result.alert_ref == "ponta verde"


def test_extract_openai_error_falls_back(monkeypatch: pytest.MonkeyPatch) -> None:
    def mock_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="err", request=request)

    transport = httpx.MockTransport(mock_handler)
    real_async_client = httpx.AsyncClient

    def custom_async_client(*args, **kwargs):
        kwargs["transport"] = transport
        return real_async_client(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", custom_async_client)

    result = asyncio.run(
        extract_assistant_intent("remover alerta de farol", provider="openai", api_key="k")
    )
    assert result.tool == "remover_alertas"

    _ = extract_assistant_intent_with_openai  # import sanity
