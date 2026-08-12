import os
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from dotenv import load_dotenv

load_dotenv()

DATA_DIR = Path(__file__).resolve().parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH = DATA_DIR / "imoveis.db"

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

# Entre uma requisição ao OLX e outra esperamos 2–5 s
SCRAPER_DELAY_MIN = float(os.getenv("SCRAPER_DELAY_MIN", "2.0"))
SCRAPER_DELAY_MAX = float(os.getenv("SCRAPER_DELAY_MAX", "5.0"))

# Número máximo de páginas a iterar (proteção contra loop infinito)
SCRAPER_MAX_PAGES = int(os.getenv("SCRAPER_MAX_PAGES", "130"))

# Marcador textual do estado "sem resultados" do OLX (fim normal da listagem)
OLX_EMPTY_RESULTS_TEXT = os.getenv("OLX_EMPTY_RESULTS_TEXT", "Nenhum anúncio foi encontrado")

# Coleta agendada (cron diário)
SCRAPE_CRON_HOUR = int(os.getenv("SCRAPE_CRON_HOUR", "8"))
SCRAPE_CRON_MINUTE = int(os.getenv("SCRAPE_CRON_MINUTE", "0"))
SCRAPE_TIMEZONE_NAME = os.getenv("SCRAPE_TIMEZONE", "America/Maceio").strip()
if not SCRAPE_TIMEZONE_NAME:
    raise RuntimeError("SCRAPE_TIMEZONE não pode ser vazio")
try:
    SCRAPE_TIMEZONE = ZoneInfo(SCRAPE_TIMEZONE_NAME)
except ZoneInfoNotFoundError as e:
    raise RuntimeError(
        f"SCRAPE_TIMEZONE inválido: {SCRAPE_TIMEZONE_NAME!r}. Use um ID IANA (ex.: America/Maceio)."
        "No Windows instale o pacote PyPI 'tzdata' se a base de fusos não estiver disponível."
    ) from e

# URLs do OLX
_OLX_BASE_DEFAULT = "https://www.olx.com.br"
OLX_BASE_URL = (os.getenv("OLX_BASE_URL", _OLX_BASE_DEFAULT).strip() or _OLX_BASE_DEFAULT).rstrip("/")
MACEIO_RENT_LISTINGS_URL = os.getenv(
    "MACEIO_RENT_LISTINGS_URL",
    f"{OLX_BASE_URL}/imoveis/aluguel/estado-al/alagoas/maceio",
).strip()
OLX_REFERER = (os.getenv("OLX_REFERER") or f"{OLX_BASE_URL}/").strip()

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