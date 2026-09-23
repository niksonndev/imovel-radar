import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


def normalize_database_url(url: str) -> str:
    """Garante o dialeto ``postgresql+psycopg`` (psycopg3).

    SQLAlchemy trata ``postgresql://`` / ``postgres://`` como psycopg2, mas
    este app depende só de ``psycopg[binary]``. URLs do SSM/Neon costumam
    vir sem o sufixo ``+psycopg``.
    """
    for prefix in ("postgresql+psycopg2://", "postgresql://", "postgres://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix) :]
    return url


# URL de conexão do Postgres. Em produção, defina DATABASE_URL (ex.: Neon).
# O default aponta para o container local de desenvolvimento (pg-local).
DATABASE_URL = normalize_database_url(
    os.getenv("DATABASE_URL", "").strip()
    or "postgresql+psycopg://postgres:teste123@localhost:5432/imovel_radar"
)

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

# Entre uma requisição ao OLX e outra esperamos 2–4 s
SCRAPER_DELAY_MIN = float(os.getenv("SCRAPER_DELAY_MIN", "2.0"))
SCRAPER_DELAY_MAX = float(os.getenv("SCRAPER_DELAY_MAX", "4.0"))

# Número máximo de páginas a iterar por fatia (proteção contra loop infinito).
# Cada fatia de preço fica abaixo do teto de paginação da OLX (~5k ads).
SCRAPER_MAX_PAGES = int(os.getenv("SCRAPER_MAX_PAGES", "500"))

# HTTP 403/429/502: tentativas dentro da mesma invocação, com UA novo.
SCRAPER_FETCH_RETRIES = int(os.getenv("SCRAPER_FETCH_RETRIES", "3"))
# Falhas da mesma página em invocações seguidas antes de pulá-la (sem completed).
SCRAPER_PAGE_MAX_ATTEMPTS = int(os.getenv("SCRAPER_PAGE_MAX_ATTEMPTS", "3"))

# Fatias (ps inclusive, pe inclusive). None = lado aberto.
# Cada URL fica abaixo do teto de paginação da OLX (~5k anúncios / 100 páginas).
PriceSlice = tuple[int | None, int | None]

# Venda Maceió. Medido em 23 set 2026: maior fatia 3.504.
SALE_PRICE_SLICES: tuple[PriceSlice, ...] = (
    (None, 300_000),
    (300_000, 500_000),
    (500_000, 700_000),
    (700_000, 1_000_000),
    (1_000_000, None),
)

# Aluguel Recife (~8.020). Uma fatia só passaria da página 100.
RECIFE_RENT_SLICES: tuple[PriceSlice, ...] = (
    (None, 3_000),
    (3_000, 5_000),
    (5_000, None),
)

# Venda Recife (~41.259). Cortada para cada faixa ficar abaixo de ~4.500.
RECIFE_SALE_SLICES: tuple[PriceSlice, ...] = (
    (None, 250_000),
    (250_000, 350_000),
    (350_000, 400_000),
    (400_000, 450_000),
    (450_000, 500_000),
    (500_000, 550_000),
    (550_000, 600_000),
    (600_000, 700_000),
    (700_000, 900_000),
    (900_000, 1_200_000),
    (1_200_000, 1_400_000),
    (1_400_000, 1_800_000),
    (1_800_000, 2_500_000),
    (2_500_000, None),
)

# Marcador textual do estado "sem resultados" do OLX (fim normal da listagem)
OLX_EMPTY_RESULTS_TEXT = os.getenv("OLX_EMPTY_RESULTS_TEXT", "Nenhum anúncio foi encontrado")

# URLs do OLX
_OLX_BASE_DEFAULT = "https://www.olx.com.br"
OLX_BASE_URL = (os.getenv("OLX_BASE_URL", _OLX_BASE_DEFAULT).strip() or _OLX_BASE_DEFAULT).rstrip("/")
MACEIO_RENT_LISTINGS_URL = os.getenv(
    "MACEIO_RENT_LISTINGS_URL",
    f"{OLX_BASE_URL}/imoveis/aluguel/estado-al/alagoas/maceio",
).strip()
MACEIO_SALE_LISTINGS_URL = os.getenv(
    "MACEIO_SALE_LISTINGS_URL",
    f"{OLX_BASE_URL}/imoveis/venda/estado-al/alagoas/maceio",
).strip()
RECIFE_RENT_LISTINGS_URL = os.getenv(
    "RECIFE_RENT_LISTINGS_URL",
    f"{OLX_BASE_URL}/imoveis/aluguel/estado-pe/grande-recife/recife",
).strip()
RECIFE_SALE_LISTINGS_URL = os.getenv(
    "RECIFE_SALE_LISTINGS_URL",
    f"{OLX_BASE_URL}/imoveis/venda/estado-pe/grande-recife/recife",
).strip()
OLX_REFERER = (os.getenv("OLX_REFERER") or f"{OLX_BASE_URL}/").strip()


@dataclass(frozen=True)
class Market:
    """Uma cidade coletada: URLs de aluguel/venda e fatias de preço."""

    key: str
    municipality: str
    rent_url: str
    sale_url: str
    rent_slices: tuple[PriceSlice, ...]
    sale_slices: tuple[PriceSlice, ...]


# Maceió primeiro: o notify das 10:00 ainda vê a cidade atual antes de Recife.
MARKETS: tuple[Market, ...] = (
    Market(
        key="maceio",
        municipality="Maceió",
        rent_url=MACEIO_RENT_LISTINGS_URL,
        sale_url=MACEIO_SALE_LISTINGS_URL,
        rent_slices=((None, None),),
        sale_slices=SALE_PRICE_SLICES,
    ),
    Market(
        key="recife",
        municipality="Recife",
        rent_url=RECIFE_RENT_LISTINGS_URL,
        sale_url=RECIFE_SALE_LISTINGS_URL,
        rent_slices=RECIFE_RENT_SLICES,
        sale_slices=RECIFE_SALE_SLICES,
    ),
)


def market_by_key(key: str | None) -> Market:
    """Evento sem ``market`` (ou chave desconhecida) continua em Maceió."""
    if key:
        for market in MARKETS:
            if market.key == key:
                return market
    return MARKETS[0]


def next_market(key: str | None) -> Market | None:
    current = market_by_key(key)
    keys = [market.key for market in MARKETS]
    index = keys.index(current.key) + 1
    if index >= len(MARKETS):
        return None
    return MARKETS[index]


# Páginas por invocação Lambda (cabe no timeout com margem para um GET de 90s)
SCRAPER_PAGES_PER_INVOKE = int(os.getenv("SCRAPER_PAGES_PER_INVOKE", "50"))
# Para a coleta se restarem menos que isto (ms) — um GET pode levar até 90s
SCRAPER_REMAINING_TIME_BUDGET_MS = int(os.getenv("SCRAPER_REMAINING_TIME_BUDGET_MS", "90000"))

# Porta do servidor FastAPI
API_PORT = int(os.getenv("API_PORT", "8000"))

# User-Agents
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
]
USER_AGENTS = [ua.strip() for ua in USER_AGENTS if ua and str(ua).strip()]
if not USER_AGENTS:
    raise RuntimeError("USER_AGENTS está vazio. Defina pelo menos um User-Agent em config.py")
