"""Conversão de valores monetários — sem dependências além de stdlib e pydantic."""

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


def fee_amount(value: object) -> int:
    """Valor de condomínio/IPTU a somar. Zero, ausente ou inválido não entra."""
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        return 0
    if isinstance(value, str):
        parsed = money_to_int(value)
        amount = parsed if parsed is not None else 0
    else:
        amount = int(value)
    return amount if amount > 0 else 0


def effective_listing_price(
    price_value: int | None,
    *,
    listing_kind: str | None,
    condominio: object = None,
    iptu: object = None,
) -> int | None:
    """Preço que o usuário paga. No aluguel, soma condomínio e IPTU quando > 0.

    Venda (e qualquer outro tipo) fica só com o preço pedido. IPTU entra no
    valor gravado pelo anúncio, sem dividir por 12.
    """
    if price_value is None or listing_kind != "aluguel":
        return price_value
    return price_value + fee_amount(condominio) + fee_amount(iptu)


def format_listing_price(
    price_value: int | None,
    *,
    listing_kind: str | None,
    condominio: object = None,
    iptu: object = None,
) -> str:
    """Total formatado. No aluguel com taxas, inclui a composição na mesma linha."""
    total = effective_listing_price(
        price_value,
        listing_kind=listing_kind,
        condominio=condominio,
        iptu=iptu,
    )
    condo = fee_amount(condominio)
    tax = fee_amount(iptu)
    if price_value is None or listing_kind != "aluguel" or (condo == 0 and tax == 0):
        return format_brl(total)
    parts = [f"aluguel {format_brl(price_value)}"]
    if condo:
        parts.append(f"cond. {format_brl(condo)}")
    if tax:
        parts.append(f"IPTU {format_brl(tax)}")
    return f"{format_brl(total)} ({' + '.join(parts)})"