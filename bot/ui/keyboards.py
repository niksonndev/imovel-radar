"""
Teclados inline do Telegram para o menu principal e para o wizard de alerta.

Cada botão usa ``callback_data`` (até 64 bytes) para o ``CallbackQueryHandler``
associado — por isso bairros usam ``nbd_<índice>`` em vez do nome completo.

Callbacks *Meus alertas*: ``mal_m`` (menu), ``mal_b`` (lista), ``mal_p_<id>``,
``mal_ed_<id>``, ``mal_rm_<id>``.
"""

from __future__ import annotations

from typing import Any

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
    """
    Usa índice em ``callback_data`` (``nbd_0``, …), não o nome do bairro:
    limite de 64 bytes do Telegram e só bairros da lista carregada são aceitos.
    """
    # Limite defensivo para evitar teclados gigantes e manter UX aceitável no Telegram.
    items = neighbourhoods[:24]
    buttons: list[list[InlineKeyboardButton]] = []
    for i in range(0, len(items), 2):
        # Monta duas colunas por linha para caber melhor em telas pequenas.
        row: list[InlineKeyboardButton] = []
        for j in (i, i + 1):
            if j >= len(items):
                break
            n = items[j]
            row.append(
                InlineKeyboardButton(
                    ("✓ " if n in selected else "") + n[:18],
                    callback_data=f"nbd_{j}",
                )
            )
        # Cada linha é adicionada mesmo quando há apenas 1 botão (quantidade ímpar).
        buttons.append(row)
    # Botão de término explícito para encerrar seleção sem depender de timeout/comando.
    buttons.append([InlineKeyboardButton("Concluir bairros", callback_data="nbd_done")])
    return InlineKeyboardMarkup(buttons)


def main_menu_keyboard() -> InlineKeyboardMarkup:
    """
    Menu principal que aparece no `/start`.

    callback_data:
      - novo_alerta
      - menu_meus_alertas
      - menu_watchlist
      - menu_ajuda
    """
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🔔 Novo Alerta", callback_data="novo_alerta")],
            [
                InlineKeyboardButton(
                    "📋 Meus Alertas", callback_data="menu_meus_alertas"
                )
            ],
            [
                InlineKeyboardButton(
                    "👀 Acompanhar anúncio", callback_data="menu_watchlist"
                )
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


def _meus_alertas_pick_button_label(alert: dict[str, Any]) -> str:
    """Rótulo do botão de escolha (limite 64 caracteres do Telegram)."""
    name = str(alert.get("alert_name") or "Sem nome").strip() or "Sem nome"
    prefix = "▶ "
    max_name = 64 - len(prefix)
    return prefix + name[:max_name]


def meus_alertas_pick_keyboard(alerts: list[dict[str, Any]]) -> InlineKeyboardMarkup:
    """
    Um botão por alerta (``mal_p_<id>``) + retorno ao menu (``mal_m``).

    ``alerts`` deve coincidir com os alertas exibidos no texto da mensagem.
    """
    rows: list[list[InlineKeyboardButton]] = [
        [
            InlineKeyboardButton(
                _meus_alertas_pick_button_label(a),
                callback_data=f"mal_p_{int(a['id'])}",
            )
        ]
        for a in alerts
    ]
    rows.append(
        [InlineKeyboardButton("🏠 Menu principal", callback_data="mal_m")]
    )
    return InlineKeyboardMarkup(rows)


def meus_alertas_empty_keyboard() -> InlineKeyboardMarkup:
    """Listagem vazia: só volta ao menu principal."""
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("🏠 Menu principal", callback_data="mal_m")]]
    )


def meus_alertas_detail_keyboard(alert_id: int) -> InlineKeyboardMarkup:
    """Detalhe de um alerta: editar, remover, voltar à lista (``mal_b``)."""
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✏️ Editar", callback_data=f"mal_ed_{alert_id}"),
                InlineKeyboardButton("🗑️ Remover", callback_data=f"mal_rm_{alert_id}"),
            ],
            [InlineKeyboardButton("⬅️ Voltar à lista", callback_data="mal_b")],
        ]
    )


def meus_alertas_edit_stub_keyboard(alert_id: int) -> InlineKeyboardMarkup:
    """Após tocar em Editar (stub): volta ao detalhe do mesmo alerta."""
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("⬅️ Voltar ao alerta", callback_data=f"mal_p_{alert_id}")],
        ]
    )
