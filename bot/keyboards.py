"""
TECLADOS do Telegram: botões que o usuário toca (inline) em vez de digitar.

InlineKeyboardButton = um botão; callback_data = string que volta pro código quando clica
(é como data-custom no HTML, não aparece pro usuário).
"""
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup

# Lista de tuplas (valor_interno, texto_no_botão)
PROPERTY_TYPES = [
    ("house", "Casa"),
    ("apartment", "Apartamento"),
    ("kitnet", "Kitnet"),
    ("land", "Terreno"),
    ("commercial", "Comercial"),
]

TRANSACTIONS = [
    ("sale", "Venda"),
    ("rent", "Aluguel"),
]


def property_type_keyboard() -> InlineKeyboardMarkup:
    # List comprehension: uma linha de botões por tipo
    rows = [
        [InlineKeyboardButton(label, callback_data=f"wiz_pt_{key}")]
        for key, label in PROPERTY_TYPES
    ]
    return InlineKeyboardMarkup(rows)


def transaction_keyboard() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(label, callback_data=f"wiz_tr_{key}")]
        for key, label in TRANSACTIONS
    ]
    return InlineKeyboardMarkup(rows)


def price_range_keyboard(transaction: str) -> InlineKeyboardMarkup:
    """
    Faixas de preço inline para wizard do /novo_alerta.
    transaction: "rent" ou "sale"
    """
    if transaction == "rent":
        presets = [
            ("wiz_price_preset_rent_0", "Até R$ 800"),
            ("wiz_price_preset_rent_1", "R$ 800 – R$ 1.500"),
            ("wiz_price_preset_rent_2", "R$ 1.500 – R$ 3.000"),
            ("wiz_price_preset_rent_3", "R$ 3.000+"),
        ]
    else:
        presets = [
            ("wiz_price_preset_sale_0", "Até R$ 150k"),
            ("wiz_price_preset_sale_1", "R$ 150k – R$ 300k"),
            ("wiz_price_preset_sale_2", "R$ 300k – R$ 600k"),
            ("wiz_price_preset_sale_3", "R$ 600k+"),
        ]

    rows: list[list[InlineKeyboardButton]] = [[InlineKeyboardButton(label, callback_data=cb)] for cb, label in presets]
    rows.append([InlineKeyboardButton("Personalizado", callback_data="wiz_price_custom")])
    return InlineKeyboardMarkup(rows)


def neighborhoods_keyboard(selected: set[str]) -> InlineKeyboardMarkup:
    """
    selected = bairros já marcados (set = conjunto sem repetir).
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
    return ReplyKeyboardMarkup([["Pular"]], resize_keyboard=True, one_time_keyboard=True)


def main_menu_keyboard() -> InlineKeyboardMarkup:
    """
    Menu principal que aparece no `/start`.

    callback_data:
      - menu_novo_alerta
      - menu_meus_alertas
      - menu_ajuda
      - menu_acompanhar
    """
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("🔔 Novo Alerta", callback_data="menu_novo_alerta"),
            ],
            [
                InlineKeyboardButton("📋 Meus Alertas", callback_data="menu_meus_alertas"),
            ],
            [
                InlineKeyboardButton("❓ Ajuda", callback_data="menu_ajuda"),
            ],
            [
                InlineKeyboardButton("👁 Acompanhar Anúncio", callback_data="menu_acompanhar"),
            ],
        ]
    )


def alert_confirmation_keyboard() -> InlineKeyboardMarkup:
    """
    Confirmação antes de salvar o alerta (wizard do /novo_alerta).
    """
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ Confirmar", callback_data="wiz_confirm_yes"),
                InlineKeyboardButton("❌ Cancelar", callback_data="wiz_confirm_no"),
            ]
        ]
    )
