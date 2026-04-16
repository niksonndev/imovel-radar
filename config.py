import os
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from dotenv import load_dotenv

load_dotenv()

DATA_DIR = Path(__file__).resolve().parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH = DATA_DIR / "imoveis.db"

# Token do BotFather — obrigatório; sem ele o bot não autentica no Telegram
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
if not TELEGRAM_BOT_TOKEN:
    raise RuntimeError("Defina TELEGRAM_BOT_TOKEN no .env")

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

# Entre uma requisição ao OLX e outra esperamos 2–5 s (menos agressivo que um robô "martelando" o site)
SCRAPER_DELAY_MIN = float(os.getenv("SCRAPER_DELAY_MIN", "2.0"))
SCRAPER_DELAY_MAX = float(os.getenv("SCRAPER_DELAY_MAX", "5.0"))

# Coleta agendada (cron diário no fuso abaixo — alinha dev local e servidor UTC)
SCRAPE_CRON_HOUR = int(os.getenv("SCRAPE_CRON_HOUR", "5"))
SCRAPE_CRON_MINUTE = int(os.getenv("SCRAPE_CRON_MINUTE", "0"))
SCRAPE_TIMEZONE_NAME = os.getenv("SCRAPE_TIMEZONE", "America/Maceio").strip()
if not SCRAPE_TIMEZONE_NAME:
    raise RuntimeError("SCRAPE_TIMEZONE não pode ser vazio")
try:
    SCRAPE_TIMEZONE = ZoneInfo(SCRAPE_TIMEZONE_NAME)
except ZoneInfoNotFoundError as e:
    raise RuntimeError(
        f"SCRAPE_TIMEZONE inválido: {SCRAPE_TIMEZONE_NAME!r}. Use um ID IANA (ex.: America/Maceio). "
        "No Windows instale o pacote PyPI 'tzdata' se a base de fusos não estiver disponível."
    ) from e

# URLs do OLX usadas pelo scraper (opcionalmente sobrescreva via .env)
_OLX_BASE_DEFAULT = "https://www.olx.com.br"
# Base URL centralizada: as demais URLs de OLX derivam dela por padrão.
OLX_BASE_URL = (os.getenv("OLX_BASE_URL", _OLX_BASE_DEFAULT).strip() or _OLX_BASE_DEFAULT).rstrip("/")
MACEIO_RENT_LISTINGS_URL = os.getenv(
    "MACEIO_RENT_LISTINGS_URL",
    f"{OLX_BASE_URL}/imoveis/aluguel/estado-al/alagoas/maceio",
).strip()
OLX_REFERER = (os.getenv("OLX_REFERER") or f"{OLX_BASE_URL}/").strip()

# Lista de strings (cada User-Agent finge um navegador diferente, às vezes ajuda a não ser bloqueado)
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
]
USER_AGENTS = [ua.strip() for ua in USER_AGENTS if ua and str(ua).strip()]
if not USER_AGENTS:
    raise RuntimeError(
        "USER_AGENTS está vazio. Defina pelo menos um User-Agent em config.py "
        "(lista não vazia de strings)."
    )
