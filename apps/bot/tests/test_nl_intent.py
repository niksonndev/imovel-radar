import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from handlers.create_new_alert import CITY, CONFIRM, INTENT, KIND, PRICE, new_alert_conversation
from handlers.nl_intent import advance_nl_flow, auto_alert_name, wiz_nl_buttons_cb, wiz_nl_text
from models import CreateAlertDraft, CreateAlertWizardState, CustomContext


def test_intent_state_constant() -> None:
    assert INTENT == 8
    handler = new_alert_conversation()
    assert INTENT in handler.states
    assert CITY in handler.states


def test_auto_alert_name() -> None:
    # 1. Apto + Ponta Verde + 400 mil
    d1: CreateAlertDraft = {
        "categories": ["Apartamentos"],
        "neighbourhoods": ["Ponta Verde"],
        "max_price": 400000,
    }
    assert auto_alert_name(d1) == "Apto · Ponta Verde · até R$ 400 mil"

    # 2. Casa + 2 bairros + faixa de preço
    d2: CreateAlertDraft = {
        "categories": ["Casas"],
        "neighbourhoods": ["Ponta Negra", "Tirol"],
        "min_price": 300000,
        "max_price": 500000,
    }
    assert auto_alert_name(d2) == "Casa · Ponta Negra e Tirol · R$ 300 mil–500 mil"

    # 3. Imóvel + cidade quando sem bairros + valor em milhão
    d3: CreateAlertDraft = {
        "municipality": "Recife",
        "max_price": 1200000,
    }
    assert auto_alert_name(d3) == "Imóvel · Recife · até R$ 1,2M"


def test_advance_nl_flow_missing_municipality() -> None:
    context = MagicMock(spec=CustomContext)
    context.user_data = {
        "create_alert_draft": CreateAlertDraft(listing_kind="venda", max_price=400000),
        "create_alert_wizard_state": CreateAlertWizardState(nl_mode=True),
    }
    msg = MagicMock()
    msg.reply_text = AsyncMock()
    update = MagicMock()
    update.effective_message = msg

    state = asyncio.run(advance_nl_flow(update, context))
    assert state == CITY
    assert msg.reply_text.called
    assert "cidade" in msg.reply_text.call_args[0][0].lower()


def test_advance_nl_flow_missing_listing_kind() -> None:
    context = MagicMock(spec=CustomContext)
    context.user_data = {
        "create_alert_draft": CreateAlertDraft(municipality="Maceió", max_price=400000),
        "create_alert_wizard_state": CreateAlertWizardState(nl_mode=True),
    }
    msg = MagicMock()
    msg.reply_text = AsyncMock()
    update = MagicMock()
    update.effective_message = msg

    state = asyncio.run(advance_nl_flow(update, context))
    assert state == KIND
    assert msg.reply_text.called
    assert "comprar ou alugar" in msg.reply_text.call_args[0][0].lower()


def test_advance_nl_flow_missing_price() -> None:
    context = MagicMock(spec=CustomContext)
    context.user_data = {
        "create_alert_draft": CreateAlertDraft(municipality="Maceió", listing_kind="aluguel"),
        "create_alert_wizard_state": CreateAlertWizardState(nl_mode=True),
    }
    msg = MagicMock()
    sent_msg = MagicMock()
    sent_msg.chat_id = 123
    sent_msg.message_id = 456
    msg.reply_text = AsyncMock(return_value=sent_msg)
    update = MagicMock()
    update.effective_message = msg

    state = asyncio.run(advance_nl_flow(update, context))
    assert state == PRICE
    assert msg.reply_text.called
    reply_lower = msg.reply_text.call_args[0][0].lower()
    assert "preço" in reply_lower or "valor" in reply_lower


def test_advance_nl_flow_all_filled_advances_to_confirm() -> None:
    draft = CreateAlertDraft(
        municipality="Maceió",
        listing_kind="venda",
        max_price=400000,
        categories=["Apartamentos"],
        neighbourhoods=["Ponta Verde"],
    )
    wizard_state = CreateAlertWizardState(nl_mode=True)
    context = MagicMock(spec=CustomContext)
    context.user_data = {
        "create_alert_draft": draft,
        "create_alert_wizard_state": wizard_state,
    }
    msg = MagicMock()
    msg.reply_text = AsyncMock()
    update = MagicMock()
    update.effective_message = msg

    state = asyncio.run(advance_nl_flow(update, context))
    assert state == CONFIRM
    assert draft.get("alert_name") == "Apto · Ponta Verde · até R$ 400 mil"
    assert msg.reply_text.called
    assert "Confirmação do alerta" in msg.reply_text.call_args[0][0]


def test_wiz_nl_text_empty_returns_intent() -> None:
    context = MagicMock(spec=CustomContext)
    context.user_data = {
        "create_alert_draft": CreateAlertDraft(),
        "create_alert_wizard_state": CreateAlertWizardState(),
    }
    msg = MagicMock()
    msg.text = "   "
    msg.reply_text = AsyncMock()
    update = MagicMock()
    update.effective_message = msg

    state = asyncio.run(wiz_nl_text(update, context))
    assert state == INTENT


def test_wiz_nl_text_fallback_to_buttons_when_extraction_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = MagicMock(spec=CustomContext)
    context.user_data = {
        "create_alert_draft": CreateAlertDraft(),
        "create_alert_wizard_state": CreateAlertWizardState(),
    }
    msg = MagicMock()
    msg.text = "abc xyz"
    msg.reply_text = AsyncMock()
    update = MagicMock()
    update.effective_message = msg
    update.effective_chat = MagicMock()
    update.effective_chat.send_action = AsyncMock()

    # Simula extractor retornando None
    import handlers.nl_intent as nl_mod

    async def mock_extract(*args, **kwargs):
        return None

    monkeypatch.setattr(nl_mod, "extract_alert_intent", mock_extract)

    state = asyncio.run(wiz_nl_text(update, context))
    assert state == CITY
    assert context.user_data["create_alert_wizard_state"]["nl_mode"] is False


def test_wiz_nl_buttons_cb_switches_to_city() -> None:
    context = MagicMock(spec=CustomContext)
    context.user_data = {
        "create_alert_draft": CreateAlertDraft(),
        "create_alert_wizard_state": CreateAlertWizardState(nl_mode=True),
    }
    query = MagicMock()
    query.answer = AsyncMock()
    query.edit_message_reply_markup = AsyncMock()
    msg = MagicMock()
    msg.reply_text = AsyncMock()
    update = MagicMock()
    update.callback_query = query
    update.effective_message = msg

    state = asyncio.run(wiz_nl_buttons_cb(update, context))
    assert state == CITY
    assert context.user_data["create_alert_wizard_state"]["nl_mode"] is False
    assert query.answer.called
    assert msg.reply_text.called
