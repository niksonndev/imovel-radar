import os

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

# Número máximo de páginas a iterar no total por kind (proteção contra loop infinito).
# Venda Maceió pode passar de 100 páginas — 500 cobre ~25k ads a 50/página.
SCRAPER_MAX_PAGES = int(os.getenv("SCRAPER_MAX_PAGES", "500"))

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
OLX_REFERER = (os.getenv("OLX_REFERER") or f"{OLX_BASE_URL}/").strip()

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