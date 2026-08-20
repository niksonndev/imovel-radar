import os
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

# URL do Postgres/Neon compartilhado (ADR 0005) — a bot acessa o banco direto.
DATABASE_URL = (
    os.getenv("DATABASE_URL", "").strip()
    or "postgresql+psycopg://postgres:teste123@localhost:5432/imovel_radar"
)

ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID", "").strip()
if not ADMIN_CHAT_ID:
    # Em produção vem das env vars da Lambda; em dev, do .env. Não quebra aqui.
    ADMIN_CHAT_ID = "0"
try:
    ADMIN_CHAT_ID = int(ADMIN_CHAT_ID)
except ValueError as exc:  # pragma: no cover - só em dev mal configurado
    raise RuntimeError("ADMIN_CHAT_ID deve ser um inteiro") from exc


# ── DynamoDB — estado de conversa (ADR 0006) ────────────────────────────────
DYNAMODB_TABLE = os.getenv("DYNAMODB_TABLE", "imovel-radar-prod-conversation-state").strip()
# TTL (horas) dos drafts de conversa abandonados — coincide com a decisão do
# ADR 0006 (2–6 h; usamos 4 h).
DYNAMODB_TTL_HOURS = int(os.getenv("DYNAMODB_TTL_HOURS", "4"))

# ── Token (SSM em produção; env em dev) ─────────────────────────────────────
SSM_TOKEN_PARAM = os.getenv("SSM_TOKEN_PARAM", "/imovel-radar/prod/telegram_bot_token").strip()

_TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()


@lru_cache(maxsize=1)
def _resolve_token() -> str:
    """Resolve o token: env primeiro; senão lê do SSM Parameter Store (Lambda)."""
    if _TELEGRAM_BOT_TOKEN:
        return _TELEGRAM_BOT_TOKEN
    import boto3  # import local p/ permitir uso em dev sem AWS

    ssm = boto3.client("ssm")
    resp = ssm.get_parameter(Name=SSM_TOKEN_PARAM, WithDecryption=True)
    token = resp.get("Parameter", {}).get("Value", "").strip()
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN não resolvido (env ou SSM)")
    return token


def get_bot_token() -> str:
    """Token do bot — cacheado (uma chamada de SSM por instância quente)."""
    return _resolve_token()


# ── Dev local ────────────────────────────────────────────────────────────────
# Persistência por arquivo SOLO para dev (pnpm run dev). No serverless se usa
# DynamoDB (ADR 0006).
def get_persistence_file() -> str:
    return os.getenv("PERSISTENCE_FILE", "carousel_state.pickle").strip()
