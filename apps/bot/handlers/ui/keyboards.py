"""
Teclados inline do Telegram para o menu principal e para o wizard de alerta.
"""

from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from shared_models import Alert

NEIGHBORHOODS_PAGE_SIZE = 12
_INLINE_BTN_TEXT_MAX = 64


def _neighbourhood_button_caption(name: str, *, selected: bool) -> str:
    if selected:
        prefix, suffix = " ✅ ", ""
    else:
        prefix, suffix = " ", " "
    room = _INLINE_BTN_TEXT_MAX - len(prefix) - len(suffix)
    if room < 2:
        short = "…"
    elif len(name) <= room:
        short = name
    else:
        short = name[: max(1, room - 1)] + "…"
    text = prefix + short + suffix
    return text[:_INLINE_BTN_TEXT_MAX]


def _neighbourhoods_done_caption(n_selected: int) -> str:
    if n_selected == 0:
        return "Concluir bairros"
    if n_selected == 1:
        label = "✅ Concluir (1 selecionado)"
    else:
        label = f"✅ Concluir ({n_selected} selecionados)"
    return label[:_INLINE_BTN_TEXT_MAX]


def price_range_keyboard() -> InlineKeyboardMarkup:
    presets = [
        ("wiz_price_preset_rent_0", "Até R$ 800"),
        ("wiz_price_preset_rent_1", "R$ 800 – R$ 1.500"),
        ("wiz_price_preset_rent_2", "R$ 1.500 – R$ 3.000"),
        ("wiz_price_preset_rent_3", "R$ 3.000+"),
    ]
    rows: list[list[InlineKeyboardButton]] = [
        [InlineKeyboardButton(label, callback_data=cb)] for cb, label in presets
    ]
    rows.append([InlineKeyboardButton("Personalizado", callback_data="wiz_price_custom")])
    return InlineKeyboardMarkup(rows)


def neighborhoods_keyboard(
    selected: list[str],
    neighbourhoods: list[str],
    *,
    page: int = 0,
    per_page: int = NEIGHBORHOODS_PAGE_SIZE,
) -> InlineKeyboardMarkup:
    n = len(neighbourhoods)
    total_pages = max(1, (n + per_page - 1) // per_page) if n else 1
    page = max(0, min(page, total_pages - 1))
    start = page * per_page
    end = min(start + per_page, n)
    page_items = [(idx, neighbourhoods[idx]) for idx in range(start, end)]

    buttons: list[list[InlineKeyboardButton]] = []
    for i in range(0, len(page_items), 2):
        row: list[InlineKeyboardButton] = []
        for j in (i, i + 1):
            if j >= len(page_items):
                break
            global_idx, name = page_items[j]
            row.append(
                InlineKeyboardButton(
                    _neighbourhood_button_caption(name, selected=name in selected),
                    callback_data=f"nbd_{global_idx}",
                )
            )
        buttons.append(row)

    if total_pages > 1:
        nav_row: list[InlineKeyboardButton] = []
        if page > 0:
            nav_row.append(InlineKeyboardButton("◀", callback_data="nbd_pg_prev"))
        nav_row.append(
            InlineKeyboardButton(
                f"Página {page + 1} de {total_pages}",
                callback_data="nbd_pg_info",
            )
        )
        if page < total_pages - 1:
            nav_row.append(InlineKeyboardButton("▶", callback_data="nbd_pg_next"))
        buttons.append(nav_row)

    n_sel = len(selected)
    buttons.append(
        [
            InlineKeyboardButton(
                _neighbourhoods_done_caption(n_sel),
                callback_data="nbd_done",
            )
        ]
    )
    return InlineKeyboardMarkup(buttons)


def main_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🔔 Novo Alerta", callback_data="novo_alerta")],
            [InlineKeyboardButton("📋 Meus Alertas", callback_data="menu_meus_alertas")],
            [InlineKeyboardButton("👀 Acompanhar anúncio", callback_data="menu_watchlist")],
            [InlineKeyboardButton("❓ Ajuda", callback_data="menu_ajuda")],
        ]
    )


def alert_confirmation_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ Confirmar", callback_data="wiz_confirm_yes"),
                InlineKeyboardButton("❌ Cancelar", callback_data="wiz_confirm_no"),
            ]
        ]
    )


def _meus_alertas_pick_button_label(alert: Alert) -> str:
    name = str(alert.alert_name or "Sem nome").strip() or "Sem nome"
    prefix = "▶ "
    max_name = 64 - len(prefix)
    return prefix + name[:max_name]


def meus_alertas_pick_keyboard(alerts: list[Alert]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = [
        [
            InlineKeyboardButton(
                _meus_alertas_pick_button_label(a),
                callback_data=f"mal_p_{int(a.id)}",
            )
        ]
        for a in alerts
    ]
    rows.append([InlineKeyboardButton("🏠 Menu principal", callback_data="mal_m")])
    return InlineKeyboardMarkup(rows)


def meus_alertas_empty_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("🏠 Menu principal", callback_data="mal_m")]]
    )


def meus_alertas_detail_keyboard(alert_id: int) -> InlineKeyboardMarkup:
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
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("⬅️ Voltar ao alerta", callback_data=f"mal_p_{alert_id}")],
        ]
    )