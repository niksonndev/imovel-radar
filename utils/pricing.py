"""Conversão de valores monetários do OLX para uso no pipeline e no bot."""

from __future__ import annotations

import re

_DIGITS_RE = re.compile(r"\d+")


def money_to_int(value: str | None) -> int | None:
    """Converte preço do OLX (ex.: ``'R$ 13.000'``) para inteiro em reais (``13000``)."""
    if not isinstance(value, str):
        return None
    digits = "".join(_DIGITS_RE.findall(value))
    return int(digits) if digits else None


def format_brl(v: int | None) -> str:
    """Formata reais (int) para exibição pt-BR — ex.: ``13000`` -> ``'R$ 13.000,00'``."""
    if v is None:
        return "—"
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
