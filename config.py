"""
CONFIGURAÇÕES (tipo um .env + constantes).

Este arquivo roda assim que alguém dá "import config".
load_dotenv() lê o arquivo .env na pasta do projeto e coloca as variáveis
no ambiente — depois os.getenv("NOME") pegam os valores (parecido com process.env no Node).
"""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

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
