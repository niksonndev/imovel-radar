"""Teclados inline e reply."""
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup

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
    """Toggle bairros; callback nbd_<name>"""
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
    return ReplyKeyboardMarkup([["Pular"]], resize_keyboard=True, one_time_keyboard=True)
