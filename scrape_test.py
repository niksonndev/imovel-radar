#!/usr/bin/env python3
"""
Comando para testar o scraping do OLX direto no terminal.

Uso:
  python scrape_test.py                        # testa aluguel + venda (todos os tipos)
  python scrape_test.py --modo aluguel         # só aluguel
  python scrape_test.py --modo venda           # só venda
  python scrape_test.py --tipo apartamento     # filtra por tipo (apartamento, casa, kitnet, terreno, comercial)
  python scrape_test.py --paginas 3            # busca até 3 páginas
  python scrape_test.py --bairro Centro Farol  # filtra por bairros
  python scrape_test.py --preco-min 1000 --preco-max 3000
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("TELEGRAM_BOT_TOKEN", "fake-token-for-scrape-test")

from scraper.olx_scraper import OLXScraper, build_search_url
from scraper.parser import parse_search_page


def _fmt_money(v: float | None) -> str:
    if v is None:
        return "—"
    return f"R$ {v:,.0f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _build_filters(args: argparse.Namespace, transaction: str) -> dict:
    tipo_map = {
        "todos": "all",
        "apartamento": "apartment",
        "casa": "house",
        "kitnet": "kitnet",
        "terreno": "land",
        "comercial": "commercial",
    }
    filters: dict = {
        "transaction": transaction,
        "property_type": tipo_map.get(args.tipo, "all"),
    }
    if args.preco_min is not None:
        filters["price_min"] = args.preco_min
    if args.preco_max is not None:
        filters["price_max"] = args.preco_max
    if args.bairro:
        filters["neighborhoods"] = args.bairro
    if args.quartos is not None:
        filters["bedrooms_min"] = args.quartos
    return filters


async def run_scraping(args: argparse.Namespace) -> None:
    modos = []
    if args.modo in ("aluguel", "todos"):
        modos.append(("rent", "ALUGUEL"))
    if args.modo in ("venda", "todos"):
        modos.append(("sale", "VENDA"))

    scraper = OLXScraper()

    total_geral = 0
    for trans_key, trans_label in modos:
        filters = _build_filters(args, trans_key)
        url = build_search_url(filters)

        print(f"\n{'='*70}")
        print(f"  {trans_label} — Maceió/AL")
        print(f"{'='*70}")
        print(f"  URL: {url}")
        print(f"  Páginas: até {args.paginas}")

        filtros_ativos = []
        if filters.get("property_type") != "all":
            filtros_ativos.append(f"Tipo: {args.tipo}")
        if filters.get("price_min") or filters.get("price_max"):
            filtros_ativos.append(
                f"Preço: {_fmt_money(filters.get('price_min'))} – {_fmt_money(filters.get('price_max'))}"
            )
        if filters.get("neighborhoods"):
            filtros_ativos.append(f"Bairros: {', '.join(filters['neighborhoods'])}")
        if filters.get("bedrooms_min"):
            filtros_ativos.append(f"Quartos mínimo: {filters['bedrooms_min']}")
        if filtros_ativos:
            print(f"  Filtros: {' | '.join(filtros_ativos)}")

        print()

        try:
            ads = await scraper.search_listings(filters, max_pages=args.paginas)
        except Exception as e:
            print(f"  ❌ ERRO: {e}")
            print()
            if "403" in str(e):
                print("  ⚠️  O OLX bloqueou a requisição (Cloudflare).")
                print("     Isso acontece em servidores/VPS. Tente na sua máquina local.")
            continue

        total_geral += len(ads)
        print(f"  ✅ {len(ads)} anúncio(s) encontrado(s)\n")

        if not ads:
            print("  Nenhum anúncio encontrado.")
            print("  💡 Se você esperava resultados, pode ser bloqueio do Cloudflare.")
            print("     Rode com -v para ver detalhes dos erros.")
            continue

        for i, ad in enumerate(ads, 1):
            titulo = (ad.get("title") or "Sem título")[:60]
            preco = _fmt_money(ad.get("price"))
            bairro = ad.get("neighborhood") or "—"
            quartos = ad.get("bedrooms")
            area = ad.get("area_m2")
            url_ad = ad.get("url") or "—"
            olx_id = ad.get("olx_id") or "—"

            quartos_s = f"{quartos}q" if quartos is not None else "—"
            area_s = f"{area:g}m²" if area is not None else "—"

            print(f"  [{i:>3}] {titulo}")
            print(f"        💰 {preco}  |  🛏 {quartos_s}  |  📐 {area_s}  |  📍 {bairro}")
            print(f"        🔗 {url_ad}")
            print(f"        ID: {olx_id}")
            print()

    await scraper.close()

    print(f"{'='*70}")
    print(f"  TOTAL: {total_geral} anúncio(s)")
    print(f"{'='*70}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Testa o scraping do OLX para Maceió/AL",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--modo",
        choices=["aluguel", "venda", "todos"],
        default="todos",
        help="Tipo de transação (default: todos)",
    )
    parser.add_argument(
        "--tipo",
        choices=["todos", "apartamento", "casa", "kitnet", "terreno", "comercial"],
        default="todos",
        help="Tipo de imóvel (default: todos)",
    )
    parser.add_argument(
        "--paginas",
        type=int,
        default=2,
        help="Quantidade máxima de páginas (default: 2)",
    )
    parser.add_argument(
        "--preco-min",
        type=int,
        default=None,
        help="Preço mínimo (R$)",
    )
    parser.add_argument(
        "--preco-max",
        type=int,
        default=None,
        help="Preço máximo (R$)",
    )
    parser.add_argument(
        "--bairro",
        nargs="+",
        default=None,
        help="Bairros para filtrar (ex: --bairro Centro Farol)",
    )
    parser.add_argument(
        "--quartos",
        type=int,
        default=None,
        help="Número mínimo de quartos",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Mostra logs de debug",
    )

    args = parser.parse_args()

    level = logging.DEBUG if args.verbose else logging.WARNING
    logging.basicConfig(
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        level=level,
    )
    if not args.verbose:
        logging.getLogger("scraper").setLevel(logging.CRITICAL)
        logging.getLogger("playwright").setLevel(logging.CRITICAL)

    asyncio.run(run_scraping(args))


if __name__ == "__main__":
    main()
