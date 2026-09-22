"""
Teclados inline do Telegram para o menu principal e para o wizard de alerta.
"""

from __future__ import annotations

from shared_models.tables import Alert, WatchedListingChange
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

import config

NEIGHBORHOODS_PAGE_SIZE = 12
_INLINE_BTN_TEXT_MAX = 64


def _neighbourhood_button_caption(name: str, *, selected: bool) -> str:
    # Marcador de largura fixa (2 caracteres) para alinhar nomes selecionados
    # e não-selecionados; sem espaço à direita (o Telegram apararia de qualquer forma).
    marker = "✅ " if selected else "  "
    room = _INLINE_BTN_TEXT_MAX - len(marker)
    if room < 2:
        short = "…"
    elif len(name) <= room:
        short = name
    else:
        short = name[: max(1, room - 1)] + "…"
    return marker + short


def _neighbourhoods_done_caption(n_selected: int) -> str:
    if n_selected == 0:
        return "Concluir bairros"
    if n_selected == 1:
        label = "✅ Concluir (1 selecionado)"
    else:
        label = f"✅ Concluir ({n_selected} selecionados)"
    return label[:_INLINE_BTN_TEXT_MAX]


def listing_kind_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("🏠 Comprar", callback_data="wiz_kind_venda"),
                InlineKeyboardButton("🔑 Alugar", callback_data="wiz_kind_aluguel"),
            ]
        ]
    )


def price_range_keyboard(*, listing_kind: str = "aluguel") -> InlineKeyboardMarkup:
    if listing_kind == "venda":
        presets = [
            ("wiz_price_preset_sale_0", "Até R$ 150 mil"),
            ("wiz_price_preset_sale_1", "R$ 150 – 300 mil"),
            ("wiz_price_preset_sale_2", "R$ 300 – 500 mil"),
            ("wiz_price_preset_sale_3", "R$ 500 mil+"),
        ]
    else:
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


def rooms_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Qualquer", callback_data="wiz_rooms_any"),
                InlineKeyboardButton("1+", callback_data="wiz_rooms_1"),
                InlineKeyboardButton("2+", callback_data="wiz_rooms_2"),
            ],
            [
                InlineKeyboardButton("3+", callback_data="wiz_rooms_3"),
                InlineKeyboardButton("4+", callback_data="wiz_rooms_4"),
            ],
        ]
    )


# OLX ``listing.category`` values (exact DB strings) ↔ wizard callback slugs.
CATEGORY_APARTAMENTOS = "Apartamentos"
CATEGORY_CASAS = "Casas"
CATEGORY_QUARTOS = "Aluguel de quartos"

_CATEGORY_BY_SLUG: dict[str, str] = {
    "apto": CATEGORY_APARTAMENTOS,
    "casa": CATEGORY_CASAS,
    "quarto": CATEGORY_QUARTOS,
}

_CATEGORY_OPTIONS_ALUGUEL: list[tuple[str, str, str]] = [
    ("apto", CATEGORY_APARTAMENTOS, "Apartamento"),
    ("casa", CATEGORY_CASAS, "Casa"),
    ("quarto", CATEGORY_QUARTOS, "Quarto"),
]
_CATEGORY_OPTIONS_VENDA: list[tuple[str, str, str]] = [
    ("apto", CATEGORY_APARTAMENTOS, "Apartamento"),
    ("casa", CATEGORY_CASAS, "Casa"),
]


def category_options_for_kind(listing_kind: str) -> list[tuple[str, str, str]]:
    """Pairs of ``(slug, db_value, button_label)`` for the wizard."""
    if listing_kind == "venda":
        return list(_CATEGORY_OPTIONS_VENDA)
    return list(_CATEGORY_OPTIONS_ALUGUEL)


def category_value_for_slug(slug: str) -> str | None:
    return _CATEGORY_BY_SLUG.get(slug)


def _categories_done_caption(n_selected: int) -> str:
    if n_selected == 0:
        return "Qualquer tipo"
    if n_selected == 1:
        label = "✅ Concluir (1 selecionado)"
    else:
        label = f"✅ Concluir ({n_selected} selecionados)"
    return label[:_INLINE_BTN_TEXT_MAX]


def categories_keyboard(
    selected: list[str],
    *,
    listing_kind: str = "aluguel",
) -> InlineKeyboardMarkup:
    options = category_options_for_kind(listing_kind)
    rows: list[list[InlineKeyboardButton]] = []
    for slug, value, label in options:
        marker = "✅ " if value in selected else ""
        rows.append(
            [
                InlineKeyboardButton(
                    f"{marker}{label}"[:_INLINE_BTN_TEXT_MAX],
                    callback_data=f"wiz_cat_{slug}",
                )
            ]
        )
    rows.append(
        [
            InlineKeyboardButton(
                _categories_done_caption(len(selected)),
                callback_data="wiz_cat_done",
            )
        ]
    )
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
                callback_data=f"mal_p_{a.id}",
            )
        ]
        for a in alerts
        if a.id is not None  # table model: id é opcional antes do primeiro flush
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


def _watchlist_pick_button_label(row: WatchedListingChange) -> str:
    title = str(row.listing.title or "Sem título").strip() or "Sem título"
    prefix = "▶ "
    max_name = 64 - len(prefix)
    return prefix + title[:max_name]


def watchlist_list_keyboard(
    rows: list[WatchedListingChange],
    *,
    can_add: bool,
) -> InlineKeyboardMarkup:
    button_rows: list[list[InlineKeyboardButton]] = [
        [
            InlineKeyboardButton(
                _watchlist_pick_button_label(row),
                callback_data=f"wl_p_{row.watch.id}",
            )
        ]
        for row in rows
        if row.watch.id is not None
    ]
    if can_add:
        button_rows.append(
            [InlineKeyboardButton("➕ Adicionar por link", callback_data="wl_add")]
        )
    button_rows.append([InlineKeyboardButton("🏠 Menu principal", callback_data="wl_m")])
    return InlineKeyboardMarkup(button_rows)


def watchlist_empty_keyboard(*, can_add: bool = True) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if can_add:
        rows.append([InlineKeyboardButton("➕ Adicionar por link", callback_data="wl_add")])
    rows.append([InlineKeyboardButton("🏠 Menu principal", callback_data="wl_m")])
    return InlineKeyboardMarkup(rows)


def watchlist_detail_keyboard(watch_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🗑️ Parar de acompanhar", callback_data=f"wl_rm_{watch_id}")],
            [InlineKeyboardButton("⬅️ Voltar à lista", callback_data="wl_b")],
        ]
    )


def watchlist_confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ Confirmar", callback_data="wl_confirm_yes"),
                InlineKeyboardButton("❌ Cancelar", callback_data="wl_confirm_no"),
            ]
        ]
    )


def watchlist_cap_upsell_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [_pro_cta_button()],
            [InlineKeyboardButton("🗑 Gerenciar acompanhados", callback_data="menu_watchlist")],
            [InlineKeyboardButton("🏠 Menu principal", callback_data="wl_m")],
        ]
    )


def alert_cap_upsell_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [_pro_cta_button()],
            [InlineKeyboardButton("📋 Meus Alertas", callback_data="menu_meus_alertas")],
            [InlineKeyboardButton("🏠 Menu principal", callback_data="wl_m")],
        ]
    )


def pro_pitch_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [_pro_cta_button()],
            [InlineKeyboardButton("🏠 Menu principal", callback_data="wl_m")],
        ]
    )


def email_pro_trial_cancel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("❌ Cancelar", callback_data="email_pro_trial_cancel")],
        ]
    )


def _pro_cta_button() -> InlineKeyboardButton:
    if config.BILLING_ENABLED:
        return InlineKeyboardButton("🚀 Quero o Radar Pro", callback_data="pro_subscribe")
    return InlineKeyboardButton(
        "📧 Cadastre seu e-mail e ganhe 1 mês de Radar Pro",
        callback_data="email_pro_trial",
    )

