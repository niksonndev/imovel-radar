import os
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()


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


# URL do Postgres/Neon compartilhado (ADR 0005) — a bot acessa o banco direto.
# Em produção use a connection string *pooled* do Neon (host com ``-pooler``).
DATABASE_URL = normalize_database_url(
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

# Header X-Telegram-Bot-Api-Secret-Token (setWebhook secret_token). Obrigatório
# no webhook da Lambda; vazio só é aceitável em dev/polling.
TELEGRAM_WEBHOOK_SECRET = os.getenv("TELEGRAM_WEBHOOK_SECRET", "").strip()

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


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


# Caps freemium / Radar Pro (ADR freemium + Stars checkout).
WATCHLIST_FREE_CAP = int(os.getenv("WATCHLIST_FREE_CAP", "2"))
WATCHLIST_PRO_CAP = int(os.getenv("WATCHLIST_PRO_CAP", "10"))
ALERT_FREE_CAP = int(os.getenv("ALERT_FREE_CAP", "1"))
ALERT_PRO_CAP = int(os.getenv("ALERT_PRO_CAP", "5"))

# Radar Pro — Telegram Stars (XTR), com âncora em BRL na copy.
# ``BILLING_ENABLED=false`` pausa invoice/checkout; trial por e-mail fica ativo.
BILLING_ENABLED = _env_bool("BILLING_ENABLED", False)
EMAIL_PRO_TRIAL_DAYS = int(os.getenv("EMAIL_PRO_TRIAL_DAYS", "30"))
PRO_STARS_AMOUNT = int(os.getenv("PRO_STARS_AMOUNT", "200"))
PRO_PRICE_BRL_LABEL = os.getenv("PRO_PRICE_BRL_LABEL", "R$ 19,90").strip() or "R$ 19,90"
# Período de assinatura Stars (Bot API): exatamente 30 dias.
PRO_SUBSCRIPTION_PERIOD_SECONDS = 2592000

# ── Dev local ────────────────────────────────────────────────────────────────
# Persistência por arquivo SOLO para dev (pnpm run dev). No serverless se usa
# DynamoDB (ADR 0006).
def get_persistence_file() -> str:
    return os.getenv("PERSISTENCE_FILE", "carousel_state.pickle").strip()


# ── IA / Onboarding em linguagem natural ─────────────────────────────────────
ALERT_NL_ENABLED = _env_bool("ALERT_NL_ENABLED", True)
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "mock").strip().lower()
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini").strip()
LLM_TIMEOUT_SECONDS = float(os.getenv("LLM_TIMEOUT_SECONDS", "8.0"))

SSM_OPENAI_PARAM = os.getenv(
    "SSM_OPENAI_PARAM", "/imovel-radar/prod/openai_api_key"
).strip()
_OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()


@lru_cache(maxsize=1)
def resolve_openai_api_key() -> str:
    """Resolve a OpenAI API key: env primeiro; senão lê do SSM Parameter Store (Lambda)."""
    if _OPENAI_API_KEY:
        return _OPENAI_API_KEY
    if not SSM_OPENAI_PARAM:
        return ""
    try:
        import boto3

        ssm = boto3.client("ssm")
        resp = ssm.get_parameter(Name=SSM_OPENAI_PARAM, WithDecryption=True)
        return resp.get("Parameter", {}).get("Value", "").strip()
    except Exception:
        return ""

