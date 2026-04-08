"""
CONFIGURAÇÕES (tipo um .env + constantes).

Este arquivo roda assim que alguém dá "import config".
load_dotenv() lê o arquivo .env na pasta do projeto e coloca as variáveis
no ambiente — depois os.getenv("NOME") pegam os valores (parecido com process.env no Node).
"""

import os
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from dotenv import load_dotenv

load_dotenv()


def _validate_olx_https_url(url: str, *, field_name: str) -> str:
    """
    Evita URLs arbitrárias em variáveis de ambiente (ex.: SSRF se alguém alterar o .env).

    Exige HTTPS e host terminando em ``olx.com.br``.
    """
    raw = (url or "").strip()
    if not raw:
        raise RuntimeError(f"{field_name} não pode ser vazio")
    parsed = urlparse(raw)
    if parsed.scheme != "https":
        raise RuntimeError(f"{field_name} deve usar HTTPS (recebido: {parsed.scheme!r})")
    netloc = (parsed.netloc or "").lower()
    if "@" in netloc:
        netloc = netloc.split("@")[-1]
    host = netloc.split(":")[0] if netloc.startswith("[") is False else netloc
    # Não usar apenas endswith("olx.com.br"): aceitaria hosts como ``evilolx.com.br``.
    if not (host == "olx.com.br" or host.endswith(".olx.com.br")):
        raise RuntimeError(
            f"{field_name} deve apontar para o domínio OLX (olx.com.br ou *.olx.com.br); "
            f"host recebido: {host!r}"
        )
    return raw


def _env_float(name: str, default: float, *, min_value: float, max_value: float) -> float:
    """Lê float do ambiente com limites; ausência ou vazio usa default."""
    raw = os.getenv(name)
    if raw is None or not str(raw).strip():
        return default
    try:
        value = float(str(raw).strip().replace(",", "."))
    except ValueError as e:
        raise RuntimeError(f"{name} deve ser um número válido") from e
    if not (min_value <= value <= max_value):
        raise RuntimeError(
            f"{name} deve estar entre {min_value} e {max_value} (recebido: {value})"
        )
    return value


def _env_int(name: str, default: int, *, min_value: int, max_value: int) -> int:
    """Lê inteiro do ambiente com limites; ausência ou vazio usa default."""
    raw = os.getenv(name)
    if raw is None or not str(raw).strip():
        return default
    try:
        value = int(str(raw).strip(), 10)
    except ValueError as e:
        raise RuntimeError(f"{name} deve ser um inteiro válido") from e
    if not (min_value <= value <= max_value):
        raise RuntimeError(
            f"{name} deve estar entre {min_value} e {max_value} (recebido: {value})"
        )
    return value


DATA_DIR = Path(__file__).resolve().parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH = DATA_DIR / "imoveis.db"

# Token do BotFather — obrigatório; sem ele o bot não autentica no Telegram
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
if not TELEGRAM_BOT_TOKEN:
    raise RuntimeError("Defina TELEGRAM_BOT_TOKEN no .env")

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

# Entre uma requisição ao OLX e outra esperamos 2–5 s (menos agressivo que um robô "martelando" o site)
SCRAPER_DELAY_MIN = _env_float("SCRAPER_DELAY_MIN", 2.0, min_value=0.0, max_value=120.0)
SCRAPER_DELAY_MAX = _env_float("SCRAPER_DELAY_MAX", 5.0, min_value=0.0, max_value=300.0)
if SCRAPER_DELAY_MIN > SCRAPER_DELAY_MAX:
    raise RuntimeError(
        "SCRAPER_DELAY_MIN não pode ser maior que SCRAPER_DELAY_MAX "
        f"({SCRAPER_DELAY_MIN} > {SCRAPER_DELAY_MAX})"
    )

# Coleta agendada (cron diário no fuso abaixo — alinha dev local e servidor UTC)
SCRAPE_CRON_HOUR = _env_int("SCRAPE_CRON_HOUR", 5, min_value=0, max_value=23)
SCRAPE_CRON_MINUTE = _env_int("SCRAPE_CRON_MINUTE", 0, min_value=0, max_value=59)
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
OLX_BASE_URL = _validate_olx_https_url(
    os.getenv("OLX_BASE_URL", _OLX_BASE_DEFAULT).strip() or _OLX_BASE_DEFAULT,
    field_name="OLX_BASE_URL",
).rstrip("/")
MACEIO_RENT_LISTINGS_URL = _validate_olx_https_url(
    os.getenv(
        "MACEIO_RENT_LISTINGS_URL",
        f"{OLX_BASE_URL}/imoveis/aluguel/estado-al/alagoas/maceio",
    ).strip(),
    field_name="MACEIO_RENT_LISTINGS_URL",
)
OLX_REFERER = _validate_olx_https_url(
    (os.getenv("OLX_REFERER") or f"{OLX_BASE_URL}/").strip(),
    field_name="OLX_REFERER",
)

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

