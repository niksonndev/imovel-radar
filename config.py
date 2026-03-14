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

# Pasta onde está este arquivo (raiz do projeto)
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)  # cria pasta data/ se não existir

# Token do BotFather — obrigatório; sem ele o bot não autentica no Telegram
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
if not TELEGRAM_BOT_TOKEN:
    raise RuntimeError("Defina TELEGRAM_BOT_TOKEN no .env")

# URL do banco: SQLite em arquivo local (não precisa instalar servidor de banco)
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    f"sqlite+aiosqlite:///{DATA_DIR / 'bot.db'}",
).strip()

# int(...) converte string para número inteiro (como Number() no JS)
ALERT_CHECK_INTERVAL_MINUTES = int(os.getenv("ALERT_CHECK_INTERVAL_MINUTES", "30"))
WATCHLIST_CHECK_INTERVAL_HOURS = int(os.getenv("WATCHLIST_CHECK_INTERVAL_HOURS", "6"))
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

# Entre uma requisição ao OLX e outra esperamos 2–5 s (menos agressivo que um robô "martelando" o site)
SCRAPER_DELAY_MIN = float(os.getenv("SCRAPER_DELAY_MIN", "2"))
SCRAPER_DELAY_MAX = float(os.getenv("SCRAPER_DELAY_MAX", "5"))

# Lista de strings (cada User-Agent finge um navegador diferente, às vezes ajuda a não ser bloqueado)
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
]

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

# dict = objeto chave→valor. Valores são os pedaços de URL que o OLX usa
PROPERTY_TYPE_SLUGS = {
    "apartment": "apartamentos",
    "house": "casas",
    "land": "terrenos",
    "commercial": "comercio-e-industria",
}

TRANSACTION_SLUGS = {"sale": "venda", "rent": "aluguel"}
