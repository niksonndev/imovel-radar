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
    assert "Preço pedido no OLX" in reply


def test_assistant_consultar_mercado_por_m2(monkeypatch) -> None:
    monkeypatch.setattr(
        assistant_mod,
        "get_latest_market_snapshot",
        AsyncMock(return_value=_snapshot()),
    )

    reply = asyncio.run(
        assistant_mod._tool_consultar_mercado(
            AssistantIntent(
                tool="consultar_mercado",
                municipality="Maceió",
                listing_kind="aluguel",
                neighbourhoods=["ponta verde"],
            ),
            metric="mean_price_m2",
        )
    )
    assert "/m²" in reply.text
    assert "R$ 40/m²" in reply.text
    assert "Preço pedido no OLX" in reply.text


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

    context = MagicMock()
    context.user_data = {}
    asyncio.run(assistant_mod.assistant_message(update, context))
    reply = update.effective_message.reply_text.call_args[0][0]
    assert "Posso salvar assim?" in reply
    assert "assistant_pending_alert" in context.user_data
    assert "reply_markup" in update.effective_message.reply_text.call_args.kwargs


def test_assistant_nada_saudacao(monkeypatch) -> None:
    update = _update("oi")
    monkeypatch.setattr(
        assistant_mod,
        "extract_assistant_intent",
        AsyncMock(return_value=AssistantIntent(tool="nada")),
    )
    asyncio.run(assistant_mod.assistant_message(update, MagicMock()))
    reply = update.effective_message.reply_text.call_args[0][0]
    assert "Posso ajudar com alertas de imóveis" in reply


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
    monkeypatch.setattr(assistant_mod, "_audio_transcription_available", lambda: True)
    monkeypatch.setattr(assistant_mod, "user_is_pro", AsyncMock(return_value=False))

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
    monkeypatch.setattr(assistant_mod, "_audio_transcription_available", lambda: True)
    monkeypatch.setattr(assistant_mod, "user_is_pro", AsyncMock(return_value=False))

    monkeypatch.setattr(assistant_mod, "_audio_to_text", AsyncMock(return_value=None))

    asyncio.run(assistant_mod.assistant_audio(update, MagicMock()))
    reply = msg.reply_text.call_args[0][0]
    assert "Não consegui transcrever" in reply


def test_assistant_audio_create_alert_requires_confirmation(monkeypatch) -> None:
    from infrastructure.ai.alert_extractor import ExtractedAlert

    msg = MagicMock()
    msg.voice = MagicMock(file_id="fid")
    msg.audio = None
    msg.reply_text = AsyncMock()
    update = MagicMock()
    update.effective_message = msg
    update.effective_user = MagicMock(id=123)
    update.effective_chat = None
    context = MagicMock()
    context.user_data = {}
    monkeypatch.setattr(assistant_mod, "_audio_transcription_available", lambda: True)
    monkeypatch.setattr(assistant_mod, "user_is_pro", AsyncMock(return_value=False))
    monkeypatch.setattr(
        assistant_mod,
        "_audio_to_text",
        AsyncMock(return_value="quero apto em ponta verde até 2000"),
    )
    monkeypatch.setattr(
        assistant_mod,
        "extract_assistant_intent",
        AsyncMock(return_value=AssistantIntent(tool="criar_alerta")),
    )
    monkeypatch.setattr(
        assistant_mod.alert_extractor,
        "extract_alert_intent",
        AsyncMock(
            return_value=ExtractedAlert(
                municipality="Maceió",
                listing_kind="aluguel",
                categories=["Apartamentos"],
                min_price=None,
                max_price=2000,
                min_rooms=None,
                neighbourhoods=["ponta verde"],
            )
        ),
    )
    monkeypatch.setattr(
        assistant_mod, "get_neighbourhoods", AsyncMock(return_value=["Ponta Verde"])
    )
    create_alert = AsyncMock()
    monkeypatch.setattr(assistant_mod, "data_create_alert", create_alert)

    asyncio.run(assistant_mod.assistant_audio(update, context))

    create_alert.assert_not_awaited()
    assert context.user_data["assistant_pending_alert"]["max_price"] == 2000
    assert "Posso salvar assim?" in msg.reply_text.call_args.args[0]
    markup = msg.reply_text.call_args.kwargs["reply_markup"]
    assert markup.inline_keyboard[0][0].callback_data.startswith("ass_cr_yes_")


def test_assistant_create_confirmation_persists_pending_alert(monkeypatch) -> None:
    token = "012345abcdef"
    pending = {
        "token": token,
        "alert_name": "Apto · Ponta Verde · até R$ 2 mil",
        "municipality": "Maceió",
        "listing_kind": "aluguel",
        "categories": ["Apartamentos"],
        "min_price": None,
        "max_price": 2000,
        "min_rooms": None,
        "neighbourhoods": ["Ponta Verde"],
    }
    query = MagicMock()
    query.data = f"ass_cr_yes_{token}"
    query.answer = AsyncMock()
    query.edit_message_text = AsyncMock()
    update = MagicMock()
    update.callback_query = query
    update.effective_user = MagicMock(id=123)
    context = MagicMock()
    context.user_data = {"assistant_pending_alert": pending}
    create_alert = AsyncMock(return_value=SimpleNamespace(status="created"))
    monkeypatch.setattr(assistant_mod, "data_create_alert", create_alert)

    asyncio.run(assistant_mod.assistant_create_confirm_cb(update, context))

    create_alert.assert_awaited_once_with(
        chat_id=123,
        alert_name=pending["alert_name"],
        min_price=None,
        max_price=2000,
        neighbourhoods=["Ponta Verde"],
        listing_kind="aluguel",
        municipality="Maceió",
        min_rooms=None,
        categories=["Apartamentos"],
    )
    assert "Alerta criado" in query.edit_message_text.call_args.args[0]
    assert "assistant_pending_alert" not in context.user_data


def test_assistant_create_confirmation_rejects_old_token() -> None:
    query = MagicMock()
    query.data = "ass_cr_yes_012345abcdef"
    query.answer = AsyncMock()
    query.edit_message_text = AsyncMock()
    update = MagicMock()
    update.callback_query = query
    update.effective_user = MagicMock(id=123)
    context = MagicMock()
    context.user_data = {
        "assistant_pending_alert": {"token": "fedcba654321"},
    }

    asyncio.run(assistant_mod.assistant_create_confirm_cb(update, context))

    assert "expirou" in query.edit_message_text.call_args.args[0]


def test_assistant_create_function_call_collects_missing_fields() -> None:
    context = MagicMock()
    context.user_data = {}

    first = asyncio.run(
        assistant_mod._tool_create_from_arguments(
            123,
            {
                "municipality": "Maceió",
                "listing_kind": "aluguel",
                "max_price": None,
            },
            context,
        )
    )
    assert "faixa de preço" in first.text
    assert "assistant_pending_alert" in context.user_data

    second = asyncio.run(
        assistant_mod._tool_create_from_arguments(
            123,
            {"municipality": None, "listing_kind": None, "max_price": 2000},
            context,
        )
    )
    assert "Posso salvar assim?" in second.text
    assert context.user_data["assistant_pending_alert"]["municipality"] == "Maceió"
    assert context.user_data["assistant_pending_alert"]["max_price"] == 2000


def test_assistant_memory_redacts_sensitive_values_and_trims() -> None:
    context = MagicMock()
    context.user_data = {}
    assistant_mod._remember_exchange(
        context,
        "meu e-mail é ana@example.com e cpf 123.456.789-00",
        "Entendi.",
    )
    assert "ana@example.com" not in context.user_data["assistant_history"][0]["content"]
    assert "123.456.789-00" not in context.user_data["assistant_history"][0]["content"]

    for index in range(assistant_mod.config.ASSISTANT_MEMORY_TURNS + 2):
        assistant_mod._remember_exchange(context, f"pedido {index}", f"resposta {index}")
    history = assistant_mod._assistant_history(context)
    assert len(history) == assistant_mod.config.ASSISTANT_MEMORY_TURNS * 2
    assert history[-1]["content"] == f"resposta {assistant_mod.config.ASSISTANT_MEMORY_TURNS + 1}"


def test_assistant_help_reflects_audio_configuration(monkeypatch) -> None:
    monkeypatch.setattr(assistant_mod.config, "LLM_PROVIDER", "mock")
    reply = assistant_mod._tool_ajuda()
    assert "não está habilitada" in reply.text


def test_assistant_audio_explains_disabled_transcription(monkeypatch) -> None:
    msg = MagicMock()
    msg.voice = MagicMock(file_id="fid")
    msg.audio = None
    msg.reply_text = AsyncMock()
    update = MagicMock()
    update.effective_message = msg
    update.effective_user = MagicMock(id=123)
    update.effective_chat = None
    context = MagicMock()
    context.user_data = {}
    monkeypatch.setattr(assistant_mod, "_audio_transcription_available", lambda: False)
    transcribe = AsyncMock()
    monkeypatch.setattr(assistant_mod, "_audio_to_text", transcribe)

    asyncio.run(assistant_mod.assistant_audio(update, context))

    transcribe.assert_not_awaited()
    assert "não está habilitada" in msg.reply_text.call_args.args[0]


def test_assistant_audio_download_error_returns_fallback(monkeypatch) -> None:
    msg = MagicMock()
    msg.voice = MagicMock(file_id="fid", mime_type="audio/ogg")
    msg.audio = None
    msg.reply_text = AsyncMock()
    update = MagicMock()
    update.effective_message = msg
    update.effective_user = MagicMock(id=123)
    update.effective_chat = None
    context = MagicMock()
    context.bot.get_file = AsyncMock(side_effect=RuntimeError("Telegram unavailable"))
    monkeypatch.setattr(assistant_mod.config, "LLM_PROVIDER", "openai")
    monkeypatch.setattr(assistant_mod.config, "resolve_openai_api_key", lambda: "key")
    monkeypatch.setattr(assistant_mod, "user_is_pro", AsyncMock(return_value=False))

    asyncio.run(assistant_mod.assistant_audio(update, context))

    context.bot.get_file.assert_awaited_once_with("fid")
    assert "Não consegui transcrever" in msg.reply_text.call_args.args[0]


def test_audio_to_text_preserves_telegram_audio_metadata(monkeypatch) -> None:
    media = SimpleNamespace(file_id="fid", file_name=None, mime_type="audio/ogg")
    telegram_file = MagicMock()
    telegram_file.download_as_bytearray = AsyncMock(return_value=bytearray(b"audio"))
    context = MagicMock()
    context.bot.get_file = AsyncMock(return_value=telegram_file)
    transcribe = AsyncMock(return_value="texto reconhecido")
    monkeypatch.setattr(assistant_mod.config, "LLM_PROVIDER", "openai")
    monkeypatch.setattr(assistant_mod.config, "resolve_openai_api_key", lambda: "key")
    monkeypatch.setattr("infrastructure.ai.transcription.transcribe_audio", transcribe)

    result = asyncio.run(assistant_mod._audio_to_text(context, media))

    assert result == "texto reconhecido"
    transcribe.assert_awaited_once_with(
        b"audio",
        api_key="key",
        filename="audio.ogg",
        content_type="audio/ogg",
    )


def test_assistant_audio_does_not_interrupt_alert_wizard(monkeypatch) -> None:
    msg = MagicMock()
    msg.voice = MagicMock(file_id="fid")
    msg.audio = None
    msg.reply_text = AsyncMock()
    update = MagicMock()
    update.effective_message = msg
    update.effective_user = MagicMock(id=123)
    update.effective_chat = None
    context = MagicMock()
    context.user_data = {"create_alert_draft": {"municipality": "Recife"}}
    transcribe = AsyncMock(return_value="some text")
    monkeypatch.setattr(assistant_mod, "_audio_to_text", transcribe)

    asyncio.run(assistant_mod.assistant_audio(update, context))

    transcribe.assert_not_awaited()
    reply = msg.reply_text.call_args.args[0]
    assert "respostas por texto" in reply
    assert "rascunho continua salvo" in reply
