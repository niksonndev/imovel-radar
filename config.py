"""
CONFIGURAÇÕES (tipo um .env + constantes).

Este arquivo roda assim que alguém dá "import config".
load_dotenv() lê o arquivo .env na pasta do projeto e coloca as variáveis
no ambiente — depois os.getenv("NOME") pegam os valores (parecido com process.env no Node).
"""

import os
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from dotenv import load_dotenv

load_dotenv()


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

DB_PATH = DATA_DIR / "new_bot.db"

# Token do BotFather — obrigatório; sem ele o bot não autentica no Telegram
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
if not TELEGRAM_BOT_TOKEN:
    raise RuntimeError("Defina TELEGRAM_BOT_TOKEN no .env")

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

# Entre uma requisição ao OLX e outra esperamos 2–5 s (menos agressivo que um robô "martelando" o site)
SCRAPER_DELAY_MIN = float(os.getenv("SCRAPER_DELAY_MIN", "2"))
SCRAPER_DELAY_MAX = float(os.getenv("SCRAPER_DELAY_MAX", "5"))

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
OLX_BASE_URL = os.getenv("OLX_BASE_URL", "https://www.olx.com.br").rstrip("/")
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

# Bairros que aparecem como botões no wizard do Telegram
MACEIO_NEIGHBORHOODS = [
    "Centro",
    "Pajuçara",
    "Ponta Verde",
    "Jatiúca",
    "Cruz das Almas",
    "Farol",
    "Gruta de Lourdes",
    "Trapiche da Barra",
    "Guaxuma",
    "Ipioca",
    "Serraria",
    "Benedito Bentes",
    "Feitosa",
    "Tabuleiro do Martins",
    "Garça Torta",
    "Pratagy",
    "Jacarecica",
    "Riacho Doce",
    "Mangabeiras",
    "Antares",
    "Santa Amélia",
    "Cidade Universitária",
    "Poço",
    "Jaraguá",
    "Mutange",
    "Fernão Veloso",
    "Barro Duro",
    "Petrópolis",
    "Pontal da Barra",
    "Ponta Grossa",
    "São Jorge",
    "Clima Bom",
    "Graciliano Ramos",
    "Ouro Preto",
]
