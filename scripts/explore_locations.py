import os
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Sequence

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    # Permite executar este script diretamente sem instalar o pacote do projeto.
    sys.path.insert(0, str(ROOT))

import config  # noqa: E402

LOGS_DIR = "logs"

os.makedirs(LOGS_DIR, exist_ok=True)

timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")


def run_query(conn, sql):
    # Helper mínimo para consultas sem parâmetros usadas só neste script exploratório.
    return conn.execute(sql).fetchall()


def get_filtered_alerts(
    conn: sqlite3.Connection,
    neighbourhoods: Sequence[str],
    min_price: int,
    max_price: int,
    municipality: str = "Maceió",
):
    # Se não há bairros-alvo, não há condição de matching para este relatório.
    if not neighbourhoods:
        return []

    if min_price > max_price:
        raise ValueError("min_price não pode ser maior que max_price")

    # Placeholders dinâmicos evitam interpolar valores diretamente na SQL.
    placeholders = ", ".join(["?"] * len(neighbourhoods))
    sql = f"""
    SELECT *
    FROM listings
    WHERE municipality = ?
      AND neighbourhood IN ({placeholders})
      AND priceValue BETWEEN ? AND ?
      AND active = 1
    ORDER BY updated_at DESC
"""
    params = [municipality, *neighbourhoods, min_price, max_price]
    return conn.execute(sql, params).fetchall()


def save_log(filename, rows, header):
    path = os.path.join(LOGS_DIR, filename)
    with open(path, "w", encoding="utf-8") as f:
        f.write(header + "\n")
        f.write("-" * 50 + "\n")
        for row in rows:
            # Layout tabular simples para inspeção manual em arquivos .log.
            f.write(f"{row[0] or '(vazio)':<40} {row[1]:>6}\n")
    print(f"Salvo em {path}")


def save_listings_log(filename, listings, header):
    path = os.path.join(LOGS_DIR, filename)
    with open(path, "w", encoding="utf-8") as f:
        f.write(header + "\n")
        f.write("-" * 120 + "\n")
        for row in listings:
            # Acesso por índice reflete ordem atual do schema da tabela `listings`.
            list_id = row[0]
            url = row[2] or "(sem url)"
            title = row[3] or "(sem titulo)"
            price_value = row[4] if row[4] is not None else "(sem preco)"
            neighbourhood = row[7] or "(sem bairro)"
            f.write(
                f"listId={list_id} | priceValue={price_value} | "
                f"neighbourhood={neighbourhood} | title={title} | url={url}\n"
            )
    print(f"Salvo em {path}")


conn = sqlite3.connect(config.DB_PATH)

# --- Neighbourhoods ---
neighbourhood_rows = run_query(
    conn,
    """
    SELECT neighbourhood, COUNT(*) as total
    FROM listings
    GROUP BY neighbourhood
    ORDER BY total DESC
""",
)

save_log(
    f"neighbourhoods_{timestamp}.log",
    neighbourhood_rows,
    f"BAIRROS — {sum(r[1] for r in neighbourhood_rows)} listings | {len(neighbourhood_rows)} bairros distintos",
)

# --- Municipalities ---
municipality_rows = run_query(
    conn,
    """
    SELECT municipality, COUNT(*) as total
    FROM listings
    GROUP BY municipality
    ORDER BY total DESC
""",
)

save_log(
    f"municipalities_{timestamp}.log",
    municipality_rows,
    f"MUNICÍPIOS — {sum(r[1] for r in municipality_rows)} listings | {len(municipality_rows)} municípios distintos",
)

# --- Neighbourhoods em Maceió ---
maceio_neighbourhood_rows = run_query(
    conn,
    """
    SELECT neighbourhood, COUNT(*) as total
    FROM listings
    WHERE municipality = 'Maceió'
    GROUP BY neighbourhood
    ORDER BY total DESC
""",
)

save_log(
    f"neighbourhoods_maceio_{timestamp}.log",
    maceio_neighbourhood_rows,
    f"BAIRROS EM MACEIÓ — {sum(r[1] for r in maceio_neighbourhood_rows)} listings | {len(maceio_neighbourhood_rows)} bairros distintos",
)

# --- Query tipo alerta do nikson: Antares, Mangabeiras, Benedito Bentes | R$ 140k–200k ---
nikson_alert_neighbourhoods = ["Antares", "Mangabeiras", "Benedito Bentes"]
nikson_alert_min_price = 140000
nikson_alert_max_price = 200000

nikson_alert_rows = get_filtered_alerts(
    conn,
    neighbourhoods=nikson_alert_neighbourhoods,
    min_price=nikson_alert_min_price,
    max_price=nikson_alert_max_price,
)

# Snapshot rápido para comparar resultado da query com a expectativa do alerta.
save_listings_log(
    f"alerta_nikson_{timestamp}.log",
    nikson_alert_rows,
    (
        f"ALERTA DO NIKSON — Maceió: {', '.join(nikson_alert_neighbourhoods)} | "
        f"priceValue {nikson_alert_min_price}–{nikson_alert_max_price} — "
        f"{len(nikson_alert_rows)} listings encontradas"
    ),
)

conn.close()
