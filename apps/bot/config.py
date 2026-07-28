import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Token do BotFather — obrigatório
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
if not TELEGRAM_BOT_TOKEN:
    raise RuntimeError("Defina TELEGRAM_BOT_TOKEN no .env")

ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID", "").strip()
if not ADMIN_CHAT_ID:
    raise RuntimeError("Defina ADMIN_CHAT_ID no .env")
try:
    ADMIN_CHAT_ID = int(ADMIN_CHAT_ID)
except ValueError as e:
    raise RuntimeError("ADMIN_CHAT_ID deve ser um inteiro") from e

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

# URL base da API do scraper (sem trailing slash)
SCRAPER_API_URL = os.getenv("SCRAPER_API_URL", "http://localhost:8000").rstrip("/")