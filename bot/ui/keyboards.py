"""
TECLADOS do Telegram: botões que o usuário toca (inline) em vez de digitar.

InlineKeyboardButton = um botão; callback_data = string que volta pro código quando clica.
"""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup

# Lista de tuplas (valor_interno, texto_no_botão)
PROPERTY_TYPES = [
    ("all", "Todos"),
    ("house", "Casa"),
    ("apartment", "Apartamento"),
    ("kitnet", "Kitnet"),
    ("land", "Terreno"),
    ("commercial", "Comercial"),
]


def property_type_keyboard() -> InlineKeyboardMarkup:
    """Retorna teclado inline com os tipos de imóvel."""
    rows = [
        [InlineKeyboardButton(label, callback_data=f"wiz_pt_{key}")]
        for key, label in PROPERTY_TYPES
    ]
    return InlineKeyboardMarkup(rows)


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


def neighborhoods_keyboard(selected: set[str] | list[str]) -> InlineKeyboardMarkup:
    """
    selected = bairros já marcados (sem repetir; set ou list para persistência pickle).
    Cada clique alterna marcar/desmarcar; "nbd_done" finaliza o passo.
    """
    from config import MACEIO_NEIGHBORHOODS

    buttons = []
    row = []
    for n in MACEIO_NEIGHBORHOODS[:24]:
        mark = "✓ " if n in selected else ""
        row.append(InlineKeyboardButton(mark + n[:18], callback_data=f"nbd_{n}"))
        if len(row) >= 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton("Concluir bairros", callback_data="nbd_done")])
    return InlineKeyboardMarkup(buttons)


def skip_keyboard() -> ReplyKeyboardMarkup:
    """Teclado normal (não inline) com uma linha "Pular" — opcional no wizard."""
    return ReplyKeyboardMarkup(
        [["Pular"]], resize_keyboard=True, one_time_keyboard=True
    )


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


def home_keyboard() -> InlineKeyboardMarkup:
    """Botão simples para voltar ao menu principal."""
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("🏠 Menu principal", callback_data="menu_home")]]
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
