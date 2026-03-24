"""
Busca listagem OLX, extrai __NEXT_DATA__, acha o primeiro anúncio (listId/adId numérico)
e imprime + grava em debug_ad.json.

Uso: python scripts/debug_parser.py
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import cloudscraper
from bs4 import BeautifulSoup

URL = (
    "https://www.olx.com.br/imoveis/aluguel/estado-al/alagoas/maceio"
)

ROOT = Path(__file__).resolve().parent.parent
OUT_JSON = ROOT / "debug_ad.json"


def _is_numeric_id(val: Any) -> bool:
    if val is None or isinstance(val, bool):
        return False
    if isinstance(val, int):
        return True
    if isinstance(val, float):
        return val.is_integer()
    if isinstance(val, str):
        return val.isdigit() and len(val) >= 1
    return False


def _first_ad_object(obj: Any, depth: int = 0) -> dict | None:
    if depth > 30 or obj is None:
        return None
    if isinstance(obj, dict):
        for key in ("listId", "adId"):
            if key in obj and _is_numeric_id(obj[key]):
                return obj
        for v in obj.values():
            found = _first_ad_object(v, depth + 1)
            if found is not None:
                return found
    elif isinstance(obj, list):
        for item in obj:
            found = _first_ad_object(item, depth + 1)
            if found is not None:
                return found
    return None


def main() -> None:
    scraper = cloudscraper.create_scraper()
    r = scraper.get(
        URL,
        timeout=90,
        headers={"Accept-Language": "pt-BR,pt;q=0.9"},
    )
    r.raise_for_status()
    html = r.text

    soup = BeautifulSoup(html, "lxml")
    script = soup.find("script", id="__NEXT_DATA__")
    if not script or not script.string:
        raise SystemExit("Tag <script id=\"__NEXT_DATA__\"> não encontrada ou vazia")

    data = json.loads(script.string)
    ad = _first_ad_object(data)
    if ad is None:
        raise SystemExit("Nenhum objeto com listId ou adId numérico encontrado")

    formatted = json.dumps(ad, indent=2, ensure_ascii=False)
    print(formatted)
    OUT_JSON.write_text(formatted + "\n", encoding="utf-8")
    print(f"Salvo: {OUT_JSON}", flush=True)


if __name__ == "__main__":
    main()
