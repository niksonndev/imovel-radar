"""
TECLADOS do Telegram: botões que o usuário toca (inline) em vez de digitar.

InlineKeyboardButton = um botão; callback_data = string que volta pro código quando clica
(é como data-custom no HTML, não aparece pro usuário).
"""
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup

# Lista de tuplas (valor_interno, texto_no_botão)
PROPERTY_TYPES = [
    ("apartment", "Apartamento"),
    ("house", "Casa"),
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
