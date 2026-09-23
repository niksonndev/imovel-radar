from handlers.create_new_alert import _removed_inline_keyboard, new_alert_conversation
from handlers.ui import menus


def test_new_alert_conversation_is_persistent() -> None:
    handler = new_alert_conversation()
    assert handler.name == "new_alert"
    assert handler.persistent is True
    assert handler.allow_reentry is True


def test_removed_inline_keyboard_sends_empty_rows() -> None:
    assert _removed_inline_keyboard().to_dict() == {"inline_keyboard": []}


def test_wizard_choice_messages_replace_the_question() -> None:
    assert menus.wizard_tipo_escolhido(listing_kind="aluguel") == "🏷️ *Tipo:* Alugar"
    assert menus.wizard_tipo_escolhido(listing_kind="venda") == "🏷️ *Tipo:* Comprar"
    assert menus.wizard_categorias_escolhido(["Apartamentos"]) == "🏠 *Tipo de imóvel:* Apartamento"
    assert menus.wizard_categorias_escolhido([]) == "🏠 *Tipo de imóvel:* qualquer"
    assert menus.wizard_quartos_escolhido(2) == "🛏 *Quartos:* 2+"
    assert menus.wizard_quartos_escolhido(None) == "🛏 *Quartos:* qualquer"
    assert menus.wizard_bairros_escolhido([]) == "📍 *Bairros:* Qualquer bairro"
    assert menus.wizard_bairros_escolhido(["Centro"]) == "📍 *Bairros:* Centro"
    assert "R$ 800,00" in menus.wizard_preco_escolhido(
        listing_kind="aluguel",
        min_price=800,
        max_price=1500,
    )
