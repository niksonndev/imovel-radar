"""Conversão de valores monetários do OLX (string, centavos) para uso no pipeline e no bot."""

from __future__ import annotations

import re
from typing import Any


def money_to_cents(value: Any) -> int | None:
    """
    Converte valores monetários do OLX para centavos (int).

    Exemplos:
    - 'R$ 2.700' -> 270000
    - 'R$ 1.234,56' -> 123456
    """
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        # Assumimos que int já vem em centavos (convenção do parser normalizado).
        return value
    if isinstance(value, float):
        # Assumimos que float já está em reais.
        return int(round(value * 100))

    s = str(value).strip()
    if not s:
        return None

    negative = s.startswith("-")
    s = s.replace("R$", "").replace("r$", "").strip()
    s = s.replace(" ", "")
    # Mantém apenas caracteres relevantes para parsing (dígitos, '.' e ',').
    s = re.sub(r"[^\d.,-]", "", s)
    if not s or s == "-":
        return None

    # Formato OLX pt-BR: milhares em '.' e decimais em ','.
    # Mas alguns casos podem vir com '.' como decimal (sem vírgula).
    if "," in s:
        s = s.replace(".", "")
        integer_part, dec_part = s.split(",", 1)
    elif "." in s:
        parts = s.split(".")
        last = parts[-1]
        # Se a última seção tiver 1-2 dígitos, tratamos como decimal; caso contrário, como milhares.
        if 1 <= len(last) <= 2:
            integer_part = "".join(parts[:-1])
            dec_part = last
        else:
            integer_part = "".join(parts)
            dec_part = ""
    else:
        integer_part = s
        dec_part = ""

    integer_digits = re.sub(r"[^\d]", "", integer_part)
    if not integer_digits:
        return None

    dec_digits = re.sub(r"[^\d]", "", dec_part)
    if not dec_digits:
        cents = int(integer_digits) * 100
    else:
        # Garante 2 dígitos (ex.: '5' => '50', '56' => '56').
        cents = int(integer_digits) * 100 + int((dec_digits + "00")[:2])

    return -cents if negative else cents


def price_value_to_float(value: Any) -> float | None:
    """
    Converte `priceValue` (string ou centavos int) para float em reais.

    Mantém a mesma convenção do restante do pipeline: centavos -> /100.
    """
    cents = money_to_cents(value)
    if cents is None:
        return None
    return cents / 100
