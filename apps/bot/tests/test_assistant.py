import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

import handlers.assistant as assistant_mod
from infrastructure.ai.assistant_intent import AssistantIntent


def _alert(**overrides):
    base = {
        "id": 1,
        "alert_name": "Apto Ponta Verde",
        "municipality": "Maceió",
        "listing_kind": "aluguel",
        "min_price": None,
        "max_price": 2000,
        "min_rooms": 2,
        "neighbourhoods": ["Ponta Verde"],
        "categories": ["Apartamentos"],
        "active": True,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def _snapshot(municipality="Maceió", kind="aluguel", mean_price=2200, nb_mean=2400):
    return {
        "cities": [
            {
                "municipality": municipality,
                "kinds": {
                    kind: {
                        "mean_price": mean_price,
                        "mean_rent_plus_condo": mean_price + 300,
                        "sample": 120,
                        "neighbourhoods": [
                            {
                                "name": "Ponta Verde",
                                "mean_price": nb_mean,
                                "mean_price_m2": 40,
                                "ranked": True,
                                "sample": 30,
                            }
                        ],
                    }
                },
            }
        ]
    }


def _update(text: str):
    msg = MagicMock()
    msg.text = text
    msg.reply_text = AsyncMock()
    update = MagicMock()
    update.effective_message = msg
    update.effective_user = MagicMock(id=123)
    return update


def test_assistant_listar_alertas(monkeypatch: pytest.MonkeyPatch) -> None:
    update = _update("quais são meus alertas")
    monkeypatch.setattr(
        assistant_mod,
        "extract_assistant_intent",
        AsyncMock(return_value=AssistantIntent(tool="listar_alertas")),
    )
    monkeypatch.setattr(assistant_mod, "get_alerts_for_user", AsyncMock(return_value=[_alert()]))
    context = MagicMock()

    asyncio.run(assistant_mod.assistant_message(update, context))
    reply = update.effective_message.reply_text.call_args[0][0]
    assert "Apto Ponta Verde" in reply


def test_assistant_remove_single_asks_confirmation(monkeypatch) -> None:
    update = _update("remove o alerta de ponta verde")
    monkeypatch.setattr(
        assistant_mod,
        "extract_assistant_intent",
        AsyncMock(return_value=AssistantIntent(tool="remover_alertas", alert_ref="ponta verde")),
    )
    monkeypatch.setattr(assistant_mod, "get_alerts_for_user", AsyncMock(return_value=[_alert()]))

    asyncio.run(assistant_mod.assistant_message(update, MagicMock()))
    args, kwargs = update.effective_message.reply_text.call_args
    assert "Confirmar remoção" in args[0]
    assert kwargs["reply_markup"] is not None


def test_assistant_consultar_mercado_city(monkeypatch) -> None:
    update = _update("média de aluguel em maceió")
    monkeypatch.setattr(
        assistant_mod,
        "extract_assistant_intent",
        AsyncMock(
            return_value=AssistantIntent(
                tool="consultar_mercado", municipality="Maceió", listing_kind="aluguel"
            )
        ),
    )
    monkeypatch.setattr(
        assistant_mod, "get_latest_market_snapshot", AsyncMock(return_value=_snapshot())
    )

    asyncio.run(assistant_mod.assistant_message(update, MagicMock()))
    reply = update.effective_message.reply_text.call_args[0][0]
    assert "Média de aluguel" in reply
    assert "R$ 2.200" in reply


def test_assistant_consultar_mercado_bairro(monkeypatch) -> None:
    update = _update("média de aluguel em ponta verde")
    monkeypatch.setattr(
        assistant_mod,
        "extract_assistant_intent",
        AsyncMock(
            return_value=AssistantIntent(
                tool="consultar_mercado",
                municipality="Maceió",
                listing_kind="aluguel",
                neighbourhoods=["ponta verde"],
            )
        ),
    )
    monkeypatch.setattr(
        assistant_mod, "get_latest_market_snapshot", AsyncMock(return_value=_snapshot())
    )

    asyncio.run(assistant_mod.assistant_message(update, MagicMock()))
    reply = update.effective_message.reply_text.call_args[0][0]
    assert "Ponta Verde" in reply
    assert "R$ 2.400" in reply


def test_assistant_cria_alerta(monkeypatch) -> None:
    update = _update("quero apto em ponta verde até 2000")
    from infrastructure.ai.alert_extractor import ExtractedAlert

    extracted = ExtractedAlert(
        municipality="Maceió",
        listing_kind="aluguel",
        categories=["Apartamentos"],
        min_price=None,
        max_price=2000,
        min_rooms=None,
        neighbourhoods=["ponta verde"],
    )
    monkeypatch.setattr(
        assistant_mod,
        "extract_assistant_intent",
        AsyncMock(return_value=AssistantIntent(tool="criar_alerta")),
    )
    monkeypatch.setattr(
        assistant_mod.alert_extractor,
        "extract_alert_intent",
        AsyncMock(return_value=extracted),
    )
    monkeypatch.setattr(
        assistant_mod, "get_neighbourhoods", AsyncMock(return_value=["Ponta Verde"])
    )
    monkeypatch.setattr(
        assistant_mod,
        "data_create_alert",
        AsyncMock(return_value=SimpleNamespace(alert_id=5, created=True, status="created")),
    )

    asyncio.run(assistant_mod.assistant_message(update, MagicMock()))
    reply = update.effective_message.reply_text.call_args[0][0]
    assert "Alerta criado" in reply


def test_assistant_nada_saudacao(monkeypatch) -> None:
    update = _update("oi")
    monkeypatch.setattr(
        assistant_mod,
        "extract_assistant_intent",
        AsyncMock(return_value=AssistantIntent(tool="nada")),
    )
    asyncio.run(assistant_mod.assistant_message(update, MagicMock()))
    reply = update.effective_message.reply_text.call_args[0][0]
    assert "assistente do Imóvel Radar" in reply


def test_remove_confirm_cb_deletes(monkeypatch) -> None:
    query = MagicMock()
    query.data = "ass_rm_yes_7"
    query.answer = AsyncMock()
    query.edit_message_text = AsyncMock()
    update = MagicMock()
    update.callback_query = query
    update.effective_user = MagicMock(id=123)
    update.effective_chat = MagicMock(id=123)

    delete_mock = AsyncMock(return_value={"message": "Alerta removido"})
    monkeypatch.setattr(assistant_mod, "data_delete_alert", delete_mock)
    monkeypatch.setattr(assistant_mod, "get_alerts_for_user", AsyncMock(return_value=[]))
    context = MagicMock()
    context.bot.send_message = AsyncMock()

    asyncio.run(assistant_mod.assistant_remove_confirm_cb(update, context))
    delete_mock.assert_awaited_once_with(7, 123)
    assert query.edit_message_text.called


def test_remove_confirm_cb_cancel() -> None:
    query = MagicMock()
    query.data = "ass_rm_no"
    query.answer = AsyncMock()
    query.edit_message_text = AsyncMock()
    update = MagicMock()
    update.callback_query = query
    update.effective_user = MagicMock(id=123)

    asyncio.run(assistant_mod.assistant_remove_confirm_cb(update, MagicMock()))
    assert query.edit_message_text.called


def test_assistant_audio_transcribes_and_responds(monkeypatch) -> None:
    msg = MagicMock()
    msg.voice = MagicMock(file_id="fid")
    msg.audio = None
    msg.reply_text = AsyncMock()
    update = MagicMock()
    update.effective_message = msg
    update.effective_user = MagicMock(id=123)
    update.effective_chat = MagicMock()
    update.effective_chat.send_action = AsyncMock()

    monkeypatch.setattr(
        assistant_mod,
        "_audio_to_text",
        AsyncMock(return_value="quais são meus alertas"),
    )
    monkeypatch.setattr(
        assistant_mod,
        "extract_assistant_intent",
        AsyncMock(return_value=AssistantIntent(tool="listar_alertas")),
    )
    monkeypatch.setattr(assistant_mod, "get_alerts_for_user", AsyncMock(return_value=[_alert()]))

    asyncio.run(assistant_mod.assistant_audio(update, MagicMock()))
    reply = msg.reply_text.call_args[0][0]
    assert "Apto Ponta Verde" in reply


def test_assistant_audio_fallback_when_no_transcription(monkeypatch) -> None:
    msg = MagicMock()
    msg.voice = MagicMock(file_id="fid")
    msg.audio = None
    msg.reply_text = AsyncMock()
    update = MagicMock()
    update.effective_message = msg
    update.effective_user = MagicMock(id=123)
    update.effective_chat = MagicMock()
    update.effective_chat.send_action = AsyncMock()

    monkeypatch.setattr(assistant_mod, "_audio_to_text", AsyncMock(return_value=None))

    asyncio.run(assistant_mod.assistant_audio(update, MagicMock()))
    reply = msg.reply_text.call_args[0][0]
    assert "Não consegui transcrever" in reply
