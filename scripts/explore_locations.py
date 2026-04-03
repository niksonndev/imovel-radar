import sqlite3
import os
from datetime import datetime

DB_PATH = "data/imoveis.db"
LOGS_DIR = "logs"

os.makedirs(LOGS_DIR, exist_ok=True)

timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")


def run_query(conn, sql):
    return conn.execute(sql).fetchall()


def save_log(filename, rows, header):
    path = os.path.join(LOGS_DIR, filename)
    with open(path, "w", encoding="utf-8") as f:
        f.write(header + "\n")
        f.write("-" * 50 + "\n")
        for row in rows:
            f.write(f"{row[0] or '(vazio)':<40} {row[1]:>6}\n")
    print(f"Salvo em {path}")


conn = sqlite3.connect(DB_PATH)

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

conn.close()
