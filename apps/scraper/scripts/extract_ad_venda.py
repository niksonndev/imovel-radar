"""
Busca listagem OLX de venda (Maceió), extrai anúncios via RSC streaming
(App Router), acha o primeiro anúncio (listId/adId numérico) e imprime +
grava fixtures; aplica normalize_olx_listing e grava o parsed.

Uso: python -m scripts.extract_ad_venda
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import cloudscraper

from collector.olx_scraper import _extract_ads_candidates, _extract_rsc_payload
from collector.parser import normalize_olx_listing

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

FIXTURES = ROOT / "tests" / "fixtures"
FIXTURES.mkdir(parents=True, exist_ok=True)

URL = "https://www.olx.com.br/imoveis/venda/estado-al/alagoas/maceio"

OUT_JSON = FIXTURES / "raw_olx_ad_venda.json"
OUT_PARSED = FIXTURES / "parsed_olx_ad_venda.json"


def _is_numeric_id(val: Any) -> bool:
    # bool é subtipo de int em Python; filtramos para evitar True/False como IDs válidos.
    if val is None or isinstance(val, bool):
        return False
    if isinstance(val, int):
        return True
    if isinstance(val, float):
        return val.is_integer()
    if isinstance(val, str):
        return val.isdigit() and len(val) >= 1
    return False


def _first_ad_object(obj: Any, depth: int = 0) -> dict[str, Any] | None:
    # Limite defensivo evita recursão excessiva em payloads inesperadamente profundos.
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


def _listing_debug_view(listing: Any) -> dict[str, Any]:
    return dict(listing)


def _print_structure_summary(ad: dict[str, Any]) -> None:
    print("=== top-level keys ===", flush=True)
    print(sorted(ad.keys()), flush=True)

    props = ad.get("properties")
    print("=== properties (name → value) ===", flush=True)
    if isinstance(props, list):
        for prop in props:
            if isinstance(prop, dict) and prop.get("name") is not None:
                print(f"  {prop.get('name')}: {prop.get('value')}", flush=True)
    else:
        print("  (ausente ou não é lista)", flush=True)


def main() -> None:
    scraper = cloudscraper.create_scraper()
    r = scraper.get(
        URL,
        timeout=90,
        headers={"Accept-Language": "pt-BR,pt;q=0.9"},
    )
    r.raise_for_status()
    html = r.text

    payload = _extract_rsc_payload(html)
    candidates = _extract_ads_candidates(payload)
    if not candidates:
        raise SystemExit("Nenhum array 'ads' encontrado no payload RSC")

    ad = _first_ad_object(candidates)
    if ad is None:
        raise SystemExit("Nenhum objeto com listId ou adId numérico encontrado")

    _print_structure_summary(ad)

    # Primeiro dump: payload cru encontrado no JSON de hidratação do front.
    formatted = json.dumps(ad, indent=2, ensure_ascii=False)
    print(formatted)
    OUT_JSON.write_text(formatted + "\n", encoding="utf-8")
    print(f"Salvo: {OUT_JSON}", flush=True)

    # Segundo dump: payload transformado para o formato usado internamente no projeto.
    parsed = normalize_olx_listing(ad, listing_kind="venda")
    parsed_text = json.dumps(parsed, indent=2, ensure_ascii=False)
    OUT_PARSED.write_text(parsed_text + "\n", encoding="utf-8")
    print(json.dumps(_listing_debug_view(parsed), indent=2, ensure_ascii=False))
    print(f"Salvo: {OUT_PARSED}", flush=True)


if __name__ == "__main__":
    main()
