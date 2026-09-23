from handlers.create_new_alert import _removed_inline_keyboard, new_alert_conversation
from handlers.ui import keyboards, menus


def test_new_alert_conversation_is_persistent() -> None:
    handler = new_alert_conversation()
    assert handler.name == "new_alert"
    assert handler.persistent is True
    assert handler.allow_reentry is True


def test_new_alert_conversation_exits_on_menu_callbacks() -> None:
    handler = new_alert_conversation()
    patterns = " ".join(
        fb.pattern.pattern for fb in handler.fallbacks if getattr(fb, "pattern", None) is not None
    )
    for token in (
        "menu_home",
        "mal_m",
        "wl_m",
        "menu_meus_alertas",
        "menu_watchlist",
        "menu_ajuda",
    ):
        assert token in patterns


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
    assert menus.wizard_cidade_escolhida("Recife") == "📍 *Cidade:* Recife"
    assert menus.wizard_cidade_escolhida("Natal") == "📍 *Cidade:* Natal"
    assert "primeira coleta" in menus.wizard_bairros_vazios()
    assert "Maceió, Recife e Natal" in menus.start_welcome()


def test_city_keyboard_has_maceio_recife_natal() -> None:
    buttons = [
        (button.text, button.callback_data)
        for row in keyboards.city_keyboard().inline_keyboard
        for button in row
    ]
    assert buttons == [
        ("Maceió", "wiz_city_maceio"),
        ("Recife", "wiz_city_recife"),
        ("Natal", "wiz_city_natal"),
    ]


def test_price_presets_depend_on_city() -> None:
    def labels(markup) -> list[str]:
        return [button.text for row in markup.inline_keyboard for button in row]

    maceio = labels(keyboards.price_range_keyboard(listing_kind="aluguel", municipality="Maceió"))
    recife = labels(keyboards.price_range_keyboard(listing_kind="aluguel", municipality="Recife"))
    recife_sale = labels(
        keyboards.price_range_keyboard(listing_kind="venda", municipality="Recife")
    )
    natal = labels(keyboards.price_range_keyboard(listing_kind="aluguel", municipality="Natal"))
    natal_sale = labels(
        keyboards.price_range_keyboard(listing_kind="venda", municipality="Natal")
    )

    assert "Até R$ 800" in maceio
    assert "Até R$ 2.500" in recife
    assert "Até R$ 800" not in recife
    assert "Até R$ 350 mil" in recife_sale
    assert "Personalizado" in recife
    assert "Personalizado" in recife_sale
    assert natal == maceio
    assert "Até R$ 800" in natal
    assert "Até R$ 150 mil" in natal_sale
