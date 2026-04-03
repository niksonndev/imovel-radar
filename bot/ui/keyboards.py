"""
TECLADOS do Telegram: botões que o usuário toca (inline) em vez de digitar.

InlineKeyboardButton = um botão; callback_data = string que volta pro código quando clica.
"""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def price_range_keyboard() -> InlineKeyboardMarkup:
    """Faixas de preço (aluguel) no wizard /novo_alerta."""
    presets = [
        ("wiz_price_preset_rent_0", "Até R$ 800"),
        ("wiz_price_preset_rent_1", "R$ 800 – R$ 1.500"),
        ("wiz_price_preset_rent_2", "R$ 1.500 – R$ 3.000"),
        ("wiz_price_preset_rent_3", "R$ 3.000+"),
    ]

    rows: list[list[InlineKeyboardButton]] = [
        [InlineKeyboardButton(label, callback_data=cb)] for cb, label in presets
    ]
    rows.append(
        [InlineKeyboardButton("Personalizado", callback_data="wiz_price_custom")]
    )
    return InlineKeyboardMarkup(rows)


def neighborhoods_keyboard(
    selected: list[str], neighbourhoods: list[str]
) -> InlineKeyboardMarkup:
    items = neighbourhoods[:24]
    buttons = [
        [
            InlineKeyboardButton(
                ("✓ " if n in selected else "") + n[:18], callback_data=f"nbd_{n}"
            )
            for n in items[i : i + 2]
        ]
        for i in range(0, len(items), 2)
    ]
    buttons.append([InlineKeyboardButton("Concluir bairros", callback_data="nbd_done")])
    return InlineKeyboardMarkup(buttons)


def main_menu_keyboard() -> InlineKeyboardMarkup:
    """
    Menu principal que aparece no `/start`.

    callback_data:
      - menu_novo_alerta
      - menu_meus_alertas
      - menu_watchlist
      - menu_status
      - menu_ajuda
    """
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🔔 Novo Alerta", callback_data="menu_novo_alerta")],
            [
                InlineKeyboardButton(
                    "📋 Meus Alertas", callback_data="menu_meus_alertas"
                )
            ],
            [
                InlineKeyboardButton("👀 Watchlist", callback_data="menu_watchlist"),
                InlineKeyboardButton("📊 Status", callback_data="menu_status"),
            ],
            [InlineKeyboardButton("❓ Ajuda", callback_data="menu_ajuda")],
        ]
    )


def alert_confirmation_keyboard() -> InlineKeyboardMarkup:
    """Confirmação antes de salvar o alerta (wizard do /novo_alerta)."""
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ Confirmar", callback_data="wiz_confirm_yes"),
                InlineKeyboardButton("❌ Cancelar", callback_data="wiz_confirm_no"),
            ]
        ]
    )
