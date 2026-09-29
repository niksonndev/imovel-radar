"""
Assistente de linguagem natural fora do wizard (Fase 1+2).

Um ``MessageHandler`` de texto livre que decide (via roteador de intenção) qual
ferramenta acionar: listar/remover/criar alertas e consultar o mercado. Ações
destrutivas (remover) exigem confirmação inline.

Roteamento: ``infrastructure/ai/assistant_intent.extract_assistant_intent``.
"""

from __future__ import annotations

import html
import inspect
import logging
import mimetypes
import re
import secrets
import threading
import time
import unicodedata
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Literal, cast

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode

import config
from handlers.data import (
    create_alert as data_create_alert,
)
from handlers.data import (
    delete_alert as data_delete_alert,
)
from handlers.data import (
    get_alerts_for_user,
    get_latest_market_snapshot,
    get_neighbourhoods,
    record_assistant_usage,
    user_is_pro,
)
from handlers.nl_intent import auto_alert_name
from infrastructure.ai import alert_extractor
from infrastructure.ai.assistant_intent import (
    MUNICIPALITIES,
    AssistantIntent,
    extract_assistant_intent,
)
from infrastructure.ai.conversation_agent import AssistantFunctionCall, call_assistant_function
from models import (
    AssistantConversationTurn,
    AssistantPendingAlert,
    CreateAlertDraft,
    CustomContext,
)

if TYPE_CHECKING:
    from shared_models.tables import Alert

logger = logging.getLogger(__name__)
_LOCAL_USAGE: dict[tuple[int, str], tuple[int, int]] = {}
_LOCAL_USAGE_LOCK = threading.Lock()

ASS_RM_YES_RE = re.compile(r"^ass_rm_yes_(\d+)$")
ASS_CR_RE = re.compile(r"^ass_cr_(yes|no)_([a-f0-9]{12})$")


@dataclass
class AssistantReply:
    text: str
    markup: InlineKeyboardMarkup | None = None


def _normalize(text: str) -> str:
    nfkd = unicodedata.normalize("NFKD", text or "")
    return "".join(c for c in nfkd if not unicodedata.combining(c)).strip().lower()


def _format_brl(value: int | None) -> str:
    if value is None:
        return "—"
    return f"R$ {value:,.0f}".replace(",", ".")


def _kind_label(kind: str | None) -> str:
    return "venda" if kind == "venda" else "aluguel"


def alert_short_line(alert: "Alert") -> str:
    nb = ", ".join(alert.neighbourhoods or []) or "qualquer bairro"
    kind = _kind_label(alert.listing_kind)
    if alert.min_price is not None and alert.max_price is not None:
        price = f"{_format_brl(alert.min_price)}–{_format_brl(alert.max_price)}"
    else:
        price = _format_brl(alert.min_price or alert.max_price)
    name = alert.alert_name or f"{kind} em {nb}"
    emoji = "🏠" if kind == "venda" else "🔑"
    return f"• {emoji} <b>{name}</b>\n   {kind} · {alert.municipality or 'Maceió'} · {nb} · {price}"


def _alerts_list_text(alerts: list["Alert"]) -> str:
    if not alerts:
        return (
            "Você ainda não tem alertas criados. Me diga, por exemplo: "
            "<b>quero um apto em Ponta Verde até R$ 2.000</b> pra eu montar um."
        )
    header = f"Você tem {len(alerts)} alerta(s):\n"
    return header + "\n" + "\n".join(alert_short_line(a) for a in alerts)


# ── Ferramentas ────────────────────────────────────────────────────────────
async def _tool_listar(chat_id: int) -> AssistantReply:
    alerts = await get_alerts_for_user(chat_id)
    text = (
        _alerts_list_text(alerts)
        + "\n\nQuer que eu remova algum? É só me dizer o nome ou o bairro."
    )
    return AssistantReply(text)


async def _tool_consultar_mercado(
    intent: AssistantIntent,
    *,
    metric: str = "mean_price",
) -> AssistantReply:
    snapshot = await get_latest_market_snapshot()
    if not snapshot:
        return AssistantReply(
            "Ainda não tenho a coleta de mercado mais recente. Tente de novo mais tarde."
        )

    municipality = intent.municipality
    if municipality is None:
        return AssistantReply("De qual cidade você quer consultar o mercado?")
    if municipality not in MUNICIPALITIES:
        return AssistantReply(
            "Ainda não cobrimos essa cidade. Hoje atendemos Maceió, Recife e Natal."
        )
    kind = intent.listing_kind
    if kind is None:
        return AssistantReply("Você quer consultar aluguel ou venda?")
    city = next(
        (c for c in snapshot.get("cities", []) if c.get("municipality") == municipality), None
    )
    if city is None:
        return AssistantReply(f"Não tenho dados de mercado para {municipality}.")
    stats = city.get("kinds", {}).get(kind)
    if not stats:
        return AssistantReply(f"Não tenho dados de {kind} para {municipality}.")

    nb_raw = (intent.neighbourhoods or [""])[0].strip()
    if nb_raw:
        available = [r.get("name", "") for r in stats.get("neighbourhoods", [])]
        matched = alert_extractor.match_neighbourhoods([nb_raw], available)
        rows = {r.get("name"): r for r in stats.get("neighbourhoods", [])}
        if matched:
            chosen = rows.get(matched[0])
            value = chosen.get(metric) if chosen is not None else None
            if chosen is not None and chosen.get("ranked") and value is not None:
                metric_label = "preço médio por m²" if metric == "mean_price_m2" else "média"
                out = (
                    f"{metric_label.capitalize()} de {kind} em <b>{chosen['name']}</b> "
                    f"({municipality}): <b>{_format_brl(value)}"
                    f"{'/m²' if metric == 'mean_price_m2' else ''}</b>"
                )
                if kind == "aluguel":
                    out += f" · {chosen.get('sample')} anúncios na amostra"
                return AssistantReply(_with_market_disclaimer(out))
        return AssistantReply(f"Sem amostra confiável de {nb_raw.title()} em {municipality}.")

    value = stats.get(metric)
    if value is None:
        return AssistantReply(f"Ainda não tenho essa métrica para {municipality}.")
    metric_label = "preço médio por m²" if metric == "mean_price_m2" else "Média"
    out = (
        f"{metric_label} de {kind} em {municipality}: "
        f"<b>{_format_brl(value)}{'/m²' if metric == 'mean_price_m2' else ''}</b>"
    )
    if (
        metric == "mean_price"
        and kind == "aluguel"
        and stats.get("mean_rent_plus_condo") is not None
    ):
        out += f" · com condomínio: <b>{_format_brl(stats['mean_rent_plus_condo'])}</b>"
    out += f" · {stats.get('sample')} anúncios na amostra"
    return AssistantReply(_with_market_disclaimer(out))


def _with_market_disclaimer(text: str) -> str:
    return text + "\n\nPreço pedido no OLX; valor pode mudar e a negociação é com o anunciante."


async def _tool_remover(chat_id: int, intent: AssistantIntent) -> AssistantReply:
    alerts = await get_alerts_for_user(chat_id)
    if not alerts:
        return AssistantReply("Você ainda não tem alertas pra remover.")

    ref = _normalize(intent.alert_ref or "")
    candidates = alerts
    if ref:
        candidates = [
            a
            for a in alerts
            if ref
            in _normalize(
                " ".join(
                    [
                        a.alert_name or "",
                        a.municipality or "",
                        " ".join(a.neighbourhoods or []),
                        a.listing_kind or "",
                    ]
                )
            )
        ]

    if not candidates:
        return AssistantReply(
            "Não achei um alerta com esse nome/bairro.\n\n" + _alerts_list_text(alerts)
        )

    if len(candidates) == 1:
        alert = candidates[0]
        text = f"Confirmar remoção deste alerta?\n\n{alert_short_line(alert)}"
        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("Sim, remover", callback_data=f"ass_rm_yes_{alert.id}"),
                    InlineKeyboardButton("Cancelar", callback_data="ass_rm_no"),
                ]
            ]
        )
        return AssistantReply(text, markup=keyboard)

    header = (
        f"Achei {len(candidates)} alertas que batem com '<b>{intent.alert_ref or ''}</b>'. "
        "Qual você quer remover? Diga o nome exato ou o bairro:\n\n"
    )
    return AssistantReply(header + "\n".join(alert_short_line(a) for a in candidates))


async def _tool_criar(
    chat_id: int,
    text: str,
    *,
    context: CustomContext | None = None,
    require_confirmation: bool = True,
) -> AssistantReply:
    extracted = await alert_extractor.extract_alert_intent(
        text,
        provider=config.LLM_PROVIDER,
        api_key=config.resolve_openai_api_key(),
        model=config.LLM_MODEL,
        timeout_s=config.LLM_TIMEOUT_SECONDS,
    )
    if extracted is None:
        return AssistantReply(
            "Não consegui entender o alerta que você quer. Tente algo como: "
            "<b>quero alugar apartamento em Ponta Verde até R$ 2.000, 2 quartos</b>."
        )
    if extracted.municipality not in MUNICIPALITIES:
        return AssistantReply("Qual cidade? (Maceió, Recife ou Natal)")
    if extracted.listing_kind not in {"aluguel", "venda"}:
        return AssistantReply("É aluguel ou venda?")
    if extracted.min_price is None and extracted.max_price is None:
        return AssistantReply(
            "Falta a faixa de preço. Ex.: <b>até R$ 2.000</b> ou <b>entre 1.500 e 3.000</b>."
        )

    neighbourhoods: list[str] = []
    if extracted.neighbourhoods:
        available = await get_neighbourhoods(
            municipality=extracted.municipality, listing_kind=extracted.listing_kind
        )
        neighbourhoods = alert_extractor.match_neighbourhoods(extracted.neighbourhoods, available)

    categories: list[str] | None = None
    if extracted.categories:
        categories = [c for c in extracted.categories]

    crit = {
        "municipality": extracted.municipality,
        "listing_kind": extracted.listing_kind,
        "categories": categories,
        "min_price": extracted.min_price,
        "max_price": extracted.max_price,
        "min_rooms": extracted.min_rooms,
        "neighbourhoods": neighbourhoods,
    }
    alert_name = auto_alert_name(crit)  # type: ignore[arg-type]

    if require_confirmation and context is not None and context.user_data is not None:
        token = secrets.token_hex(6)
        pending: AssistantPendingAlert = {
            "token": token,
            "alert_name": alert_name,
            "municipality": extracted.municipality,
            "listing_kind": extracted.listing_kind,
            "categories": categories,
            "min_price": extracted.min_price,
            "max_price": extracted.max_price,
            "min_rooms": extracted.min_rooms,
            "neighbourhoods": neighbourhoods,
        }
        context.user_data["assistant_pending_alert"] = pending
        min_price = extracted.min_price
        max_price = extracted.max_price
        if min_price is not None and max_price is not None:
            price = f"{_format_brl(min_price)} a {_format_brl(max_price)}"
        elif max_price is not None:
            price = f"até {_format_brl(max_price)}"
        else:
            price = f"a partir de {_format_brl(min_price)}"
        summary = (
            "Entendi este alerta:\n"
            f"• {alert_name}\n"
            f"• {extracted.municipality} · {extracted.listing_kind}\n"
            f"• Bairros: {', '.join(neighbourhoods) or 'qualquer bairro'}\n"
            f"• Preço: {price}\n"
            f"• Quartos: {extracted.min_rooms or 'qualquer'}\n\n"
            "Posso salvar assim?"
        )
        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("Confirmar", callback_data=f"ass_cr_yes_{token}"),
                    InlineKeyboardButton("Cancelar", callback_data=f"ass_cr_no_{token}"),
                ]
            ]
        )
        return AssistantReply(summary, markup=keyboard)

    result = await data_create_alert(
        chat_id=chat_id,
        alert_name=alert_name,
        min_price=extracted.min_price,
        max_price=extracted.max_price,
        neighbourhoods=neighbourhoods,
        listing_kind=extracted.listing_kind,
        municipality=extracted.municipality,
        min_rooms=extracted.min_rooms,
        categories=categories,
    )
    if result.status == "created":
        return AssistantReply(
            f"✅ Alerta criado: <b>{alert_name}</b>. Você começa a receber os matches."
        )
    if result.status == "reused":
        return AssistantReply(
            f"♻️ Você já tinha um alerta igual (<b>{alert_name}</b>). Nada criado."
        )
    return AssistantReply(
        "Você atingiu o limite de alertas do seu plano. Use /start pra ver "
        "as opções ou cadastre o e-mail pra ganhar Radar Pro."
    )


def _tool_ajuda() -> AssistantReply:
    if _audio_transcription_available():
        audio_help = "\nTambém aceito mensagens de voz."
    else:
        audio_help = "\nA transcrição de áudio não está habilitada agora; envie por texto."
    return AssistantReply(
        "Como posso ajudar? Posso:\n"
        "• listar seus alertas\n"
        "• remover um alerta (ex.: <b>remove o alerta de Ponta Verde</b>)\n"
        "• criar um alerta (ex.: <b>quero apto em Jatiúca até R$ 2.500</b>)\n"
        "• consultar o mercado (ex.: <b>média de aluguel em Boa Viagem?</b>)\n"
        "• ver privacidade (/privacidade) ou excluir seus dados (/excluir_dados)\n"
        "• suporte (/suporte)\n"
        f"{audio_help}\n"
    )


def _audio_transcription_available() -> bool:
    return config.LLM_PROVIDER == "openai" and bool(config.resolve_openai_api_key())


async def _consume_daily_usage(
    context: CustomContext,
    user_id: int,
    *,
    audio: bool,
    audio_seconds: int = 0,
) -> str:
    if not _audio_transcription_available():
        return "allowed"
    try:
        pro = await user_is_pro(user_id)
    except Exception:
        logger.exception("Falha ao validar entitlement do assistente")
        return "unavailable"

    message_limit = (
        config.ASSISTANT_PRO_MESSAGES_PER_DAY if pro else config.ASSISTANT_FREE_MESSAGES_PER_DAY
    )
    audio_limit = config.ASSISTANT_PRO_AUDIO_PER_DAY if pro else config.ASSISTANT_FREE_AUDIO_PER_DAY
    persistence = getattr(context.application, "persistence", None)
    consume = getattr(persistence, "consume_daily_assistant_usage", None)
    if callable(consume) and inspect.iscoroutinefunction(consume):
        try:
            allowed = await consume(
                user_id,
                audio=audio,
                message_limit=message_limit,
                audio_limit=audio_limit,
                audio_seconds=audio_seconds,
            )
        except Exception:
            logger.exception("Falha ao registrar quota diária do assistente")
            return "unavailable"
        if allowed:
            await _bump_postgres_usage(user_id, audio=audio, audio_seconds=audio_seconds)
        return "allowed" if allowed else "limited"

    day = datetime.now(UTC).date().isoformat()
    key = (user_id, day)
    with _LOCAL_USAGE_LOCK:
        messages, audios = _LOCAL_USAGE.get(key, (0, 0))
        if messages >= message_limit or (audio and audios >= audio_limit):
            return "limited"
        _LOCAL_USAGE[key] = (messages + 1, audios + int(audio))
    await _bump_postgres_usage(user_id, audio=audio, audio_seconds=audio_seconds)
    return "allowed"


async def _bump_postgres_usage(
    user_id: int,
    *,
    audio: bool,
    audio_seconds: int = 0,
) -> None:
    """Incrementa contadores (msg/áudio) na telemetria agregada do Postgres."""
    await record_assistant_usage(
        chat_id=user_id,
        message_count=1,
        audio_count=int(audio),
        audio_seconds=audio_seconds if audio else 0,
    )


async def _record_token_usage(
    context: CustomContext | None,
    user_id: int,
    tokens: int | None,
    *,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
) -> None:
    if tokens is None or tokens <= 0:
        return
    logger.info("assistant_model_usage model=%s total_tokens=%s", config.LLM_MODEL, tokens)
    persistence = getattr(getattr(context, "application", None), "persistence", None)
    record = getattr(persistence, "record_daily_assistant_tokens", None)
    if callable(record) and inspect.iscoroutinefunction(record):
        try:
            total_tokens = await record(
                user_id,
                tokens,
                input_tokens=input_tokens or 0,
                output_tokens=output_tokens or 0,
            )
            if total_tokens >= config.ASSISTANT_DAILY_TOKEN_ALERT:
                logger.warning(
                    "assistant_daily_token_limit_reached total_tokens=%s",
                    total_tokens,
                )
        except Exception:
            logger.exception("Falha ao registrar tokens do assistente")

    try:
        await record_assistant_usage(
            chat_id=user_id,
            input_tokens=input_tokens or 0,
            output_tokens=output_tokens or 0,
            total_tokens=tokens,
        )
    except Exception:
        logger.exception("Falha ao gravar tokens do assistente no Postgres")


async def _reply_for_quota(
    message,
    context: CustomContext,
    user_id: int,
    *,
    audio: bool,
    audio_seconds: int = 0,
) -> bool:
    status = await _consume_daily_usage(
        context,
        user_id,
        audio=audio,
        audio_seconds=audio_seconds,
    )
    if status == "allowed":
        return True
    if status == "limited":
        plan = "Radar Pro" if await user_is_pro(user_id) else "plano grátis"
        limit = (
            (
                config.ASSISTANT_PRO_AUDIO_PER_DAY
                if plan == "Radar Pro"
                else config.ASSISTANT_FREE_AUDIO_PER_DAY
            )
            if audio
            else (
                config.ASSISTANT_PRO_MESSAGES_PER_DAY
                if plan == "Radar Pro"
                else config.ASSISTANT_FREE_MESSAGES_PER_DAY
            )
        )
        label = "mensagens de voz" if audio else "mensagens do assistente"
        await message.reply_text(
            f"Você atingiu o limite diário de {limit} {label} do {plan}. "
            "Tente novamente após a renovação do limite."
        )
    else:
        await message.reply_text(
            "Não consegui validar seu acesso agora. Tente novamente em instantes."
        )
    return False


def _clean_memory_text(text: str) -> str:
    text = re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "[e-mail removido]", text)
    text = re.sub(r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b|\b\d{11}\b", "[documento removido]", text)
    text = re.sub(r"(?:\b\d[ -]?){13,19}\b", "[número de cartão removido]", text)
    return re.sub(r"<[^>]*>", "", text)[:1600]


def _assistant_history(context: CustomContext | None) -> list[dict[str, str]]:
    if context is None or context.user_data is None:
        return []
    updated_at = context.user_data.get("assistant_history_updated_at", 0)
    if time.time() - updated_at > config.ASSISTANT_MEMORY_TTL_SECONDS:
        context.user_data.pop("assistant_history", None)
        return []
    history = context.user_data.get("assistant_history", [])
    recent_history = history[-config.ASSISTANT_MEMORY_TURNS * 2 :]
    return [{"role": turn["role"], "content": turn["content"]} for turn in recent_history]


def _remember_exchange(
    context: CustomContext | None,
    user_text: str,
    assistant_text: str,
) -> None:
    if context is None or context.user_data is None:
        return
    history = context.user_data.setdefault("assistant_history", [])
    history.extend(
        [
            AssistantConversationTurn(role="user", content=_clean_memory_text(user_text)),
            AssistantConversationTurn(role="assistant", content=_clean_memory_text(assistant_text)),
        ]
    )
    del history[: -config.ASSISTANT_MEMORY_TURNS * 2]
    context.user_data["assistant_history_updated_at"] = time.time()


async def _tool_create_from_arguments(
    user_id: int,
    arguments: dict,
    context: CustomContext | None,
) -> AssistantReply:
    if context is None or context.user_data is None:
        return AssistantReply("Não consegui guardar o rascunho agora. Tente usar /novo_alerta.")

    previous = context.user_data.get("assistant_pending_alert", {})
    if previous.get("token"):
        previous = {}
    pending = cast(AssistantPendingAlert, dict(previous))
    for field in (
        "municipality",
        "listing_kind",
        "categories",
        "min_price",
        "max_price",
        "min_rooms",
        "neighbourhoods",
        "alert_name",
    ):
        value = arguments.get(field)
        if value is not None:
            pending[field] = value

    municipality = pending.get("municipality")
    if municipality is not None and municipality not in MUNICIPALITIES:
        context.user_data.pop("assistant_pending_alert", None)
        return AssistantReply(
            "Ainda não cobrimos essa cidade. Hoje atendemos Maceió, Recife e Natal."
        )

    min_price = pending.get("min_price")
    max_price = pending.get("max_price")
    if min_price is not None and min_price <= 0 or max_price is not None and max_price <= 0:
        return AssistantReply("O preço precisa ser maior que zero. Qual faixa você procura?")
    if min_price is not None and max_price is not None and min_price > max_price:
        return AssistantReply(
            "O valor mínimo ficou acima do máximo. Qual faixa de preço devo usar?"
        )

    kind = pending.get("listing_kind")
    price_reference = max_price if max_price is not None else min_price
    if kind is None and price_reference is not None:
        if price_reference <= 20_000:
            kind = "aluguel"
        elif price_reference >= 50_000:
            kind = "venda"
        if kind is not None:
            pending["listing_kind"] = kind

    missing: list[str] = []
    if municipality is None:
        missing.append("cidade (Maceió, Recife ou Natal)")
    if kind is None:
        missing.append("tipo: aluguel ou venda")
    if min_price is None and max_price is None:
        missing.append("faixa de preço")
    if missing:
        context.user_data["assistant_pending_alert"] = pending
        return AssistantReply("Para montar seu alerta, me diga " + " e ".join(missing) + ".")

    assert municipality is not None and kind is not None
    raw_neighbourhoods = pending.get("neighbourhoods") or []
    neighbourhoods: list[str] = []
    if raw_neighbourhoods:
        available = await get_neighbourhoods(municipality=municipality, listing_kind=kind)
        neighbourhoods = alert_extractor.match_neighbourhoods(raw_neighbourhoods, available)
        if not neighbourhoods:
            context.user_data["assistant_pending_alert"] = pending
            return AssistantReply(
                f"Não localizei {', '.join(raw_neighbourhoods)} na lista de bairros de "
                f"{municipality}. Quer tentar outro bairro ou qualquer bairro?"
            )

    categories = pending.get("categories")
    allowed_categories = {"Apartamentos", "Casas", "Aluguel de quartos"}
    categories = [item for item in categories or [] if item in allowed_categories] or None
    crit: CreateAlertDraft = {
        "municipality": municipality,
        "listing_kind": cast(Literal["aluguel", "venda"], kind),
        "categories": categories or [],
        "neighbourhoods": neighbourhoods,
    }
    if min_price is not None:
        crit["min_price"] = min_price
    if max_price is not None:
        crit["max_price"] = max_price
    min_rooms = pending.get("min_rooms")
    if min_rooms is not None:
        crit["min_rooms"] = min_rooms
    alert_name = str(pending.get("alert_name") or auto_alert_name(crit))[:120]
    token = secrets.token_hex(6)
    pending.update(
        {
            "token": token,
            "alert_name": alert_name,
            "municipality": municipality,
            "listing_kind": kind,
            "categories": categories,
            "neighbourhoods": neighbourhoods,
        }
    )
    context.user_data["assistant_pending_alert"] = pending
    price = (
        f"{_format_brl(min_price)} a {_format_brl(max_price)}"
        if min_price is not None and max_price is not None
        else f"até {_format_brl(max_price)}"
        if max_price is not None
        else f"a partir de {_format_brl(min_price)}"
    )
    summary = (
        "Entendi este alerta:\n"
        f"• {html.escape(alert_name)}\n"
        f"• {html.escape(municipality)} · {kind}\n"
        f"• Bairros: {html.escape(', '.join(neighbourhoods) or 'qualquer bairro')}\n"
        f"• Preço: {price}\n"
        f"• Quartos: {pending.get('min_rooms') or 'qualquer'}\n\n"
        "Posso salvar assim?"
    )
    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Confirmar", callback_data=f"ass_cr_yes_{token}"),
                InlineKeyboardButton("Cancelar", callback_data=f"ass_cr_no_{token}"),
            ]
        ]
    )
    return AssistantReply(summary, markup=keyboard)


async def _execute_function_call(
    user_id: int,
    call: AssistantFunctionCall,
    context: CustomContext | None,
) -> AssistantReply:
    arguments = call.arguments
    if call.name == "list_alerts":
        return await _tool_listar(user_id)
    if call.name == "create_alert":
        return await _tool_create_from_arguments(user_id, arguments, context)
    if call.name == "remove_alerts":
        return await _tool_remover(
            user_id,
            AssistantIntent(tool="remover_alertas", alert_ref=arguments.get("alert_ref")),
        )
    if call.name == "consult_market":
        intent = AssistantIntent(
            tool="consultar_mercado",
            municipality=arguments.get("municipality"),
            listing_kind=arguments.get("listing_kind"),
            neighbourhoods=arguments.get("neighbourhoods"),
        )
        return await _tool_consultar_mercado(intent, metric=arguments.get("metric", "mean_price"))
    if call.name == "help":
        return _tool_ajuda()
    return AssistantReply(
        "Posso ajudar com alertas de imóveis e dados do mercado das cidades cobertas."
    )


# ── Dispatcher ─────────────────────────────────────────────────────────────
async def _handle_text(
    message,
    user_id: int,
    text: str,
    context: CustomContext | None = None,
    *,
    confirm_create: bool = True,
) -> None:
    """Roteia com function-calling ou usa o classificador local como fallback."""
    if len(text) > config.ASSISTANT_MAX_MESSAGE_CHARS:
        await message.reply_text(
            f"Sua mensagem passou do limite de {config.ASSISTANT_MAX_MESSAGE_CHARS} caracteres. "
            "Envie um trecho menor."
        )
        return

    provider_available = config.LLM_PROVIDER == "openai" and bool(config.resolve_openai_api_key())
    call: AssistantFunctionCall | None = None
    if provider_available:
        call = await call_assistant_function(
            text,
            history=_assistant_history(context),
            api_key=config.resolve_openai_api_key(),
            model=config.LLM_MODEL,
            timeout_s=config.LLM_TIMEOUT_SECONDS,
        )

    if call is not None:
        try:
            reply = await _execute_function_call(user_id, call, context)
            await _record_token_usage(
                context,
                user_id,
                call.total_tokens,
                input_tokens=call.input_tokens,
                output_tokens=call.output_tokens,
            )
            logger.info(
                "assistant_function_call model=%s tool=%s total_tokens=%s",
                config.LLM_MODEL,
                call.name,
                call.total_tokens,
            )
        except Exception:
            logger.exception("Erro ao executar ferramenta do assistente: %s", call.name)
            reply = AssistantReply("Desculpe, não consegui concluir isso. Tente novamente.")
    else:
        intent = await extract_assistant_intent(
            text,
            provider="mock" if provider_available else config.LLM_PROVIDER,
            api_key="" if provider_available else config.resolve_openai_api_key(),
            model=config.LLM_MODEL,
            timeout_s=config.LLM_TIMEOUT_SECONDS,
        )
        if intent.tool != "criar_alerta" and context is not None and context.user_data is not None:
            context.user_data.pop("assistant_pending_alert", None)
        try:
            if intent.tool == "remover_alertas":
                reply = await _tool_remover(user_id, intent)
            elif intent.tool == "listar_alertas":
                reply = await _tool_listar(user_id)
            elif intent.tool == "consultar_mercado":
                reply = await _tool_consultar_mercado(intent)
            elif intent.tool == "criar_alerta":
                extracted = alert_extractor.mock_extract_alert(text)
                reply = await _tool_create_from_arguments(
                    user_id,
                    {
                        "municipality": extracted.municipality,
                        "listing_kind": extracted.listing_kind,
                        "categories": extracted.categories,
                        "min_price": extracted.min_price,
                        "max_price": extracted.max_price,
                        "min_rooms": extracted.min_rooms,
                        "neighbourhoods": extracted.neighbourhoods,
                    },
                    context,
                )
            elif intent.tool == "ajuda":
                reply = _tool_ajuda()
            else:
                reply = AssistantReply(
                    "Posso ajudar com alertas de imóveis e dados do mercado das cidades cobertas."
                )
        except Exception:
            logger.exception("Erro no assistente (intent=%s)", intent.tool)
            reply = AssistantReply("Desculpe, não consegui concluir isso. Tente novamente.")

    await message.reply_text(
        reply.text,
        parse_mode=ParseMode.HTML,
        reply_markup=reply.markup,
    )
    _remember_exchange(context, text, reply.text)


async def assistant_message(update: Update, context: CustomContext) -> None:
    message = update.effective_message
    user = update.effective_user
    if message is None or user is None:
        return
    text = (message.text or "").strip()
    if not text:
        return
    if len(text) > config.ASSISTANT_MAX_MESSAGE_CHARS:
        await message.reply_text(
            f"Sua mensagem passou do limite de {config.ASSISTANT_MAX_MESSAGE_CHARS} caracteres. "
            "Envie um trecho menor."
        )
        return
    if not await _reply_for_quota(message, context, user.id, audio=False):
        return
    await _handle_text(message, user.id, text, context)


async def _audio_to_text(context: CustomContext, media) -> str | None:
    """Baixa o áudio do Telegram e transcreve via Whisper."""
    from infrastructure.ai.transcription import transcribe_audio

    api_key = config.resolve_openai_api_key()
    if config.LLM_PROVIDER != "openai" or not api_key:
        return None
    try:
        file = await context.bot.get_file(media.file_id)
        raw = await file.download_as_bytearray()
    except Exception:
        logger.exception("Falha ao baixar áudio do Telegram")
        return None
    if len(raw) > config.ASSISTANT_MAX_AUDIO_BYTES:
        logger.info("assistant_audio_rejected reason=size bytes=%s", len(raw))
        return None

    content_type = getattr(media, "mime_type", None)
    filename = getattr(media, "file_name", None)
    if not filename:
        extension = mimetypes.guess_extension(content_type or "") or ".ogg"
        if extension == ".oga":
            extension = ".ogg"
        filename = f"audio{extension}"
    if not content_type or not content_type.startswith("audio/"):
        content_type = mimetypes.guess_type(filename)[0]

    text = await transcribe_audio(
        bytes(raw),
        api_key=api_key,
        filename=filename,
        content_type=content_type,
    )
    return text


async def assistant_audio(update: Update, context: CustomContext) -> None:
    message = update.effective_message
    user = update.effective_user
    if message is None or user is None:
        return
    voice = message.voice or message.audio
    if voice is None:
        return
    if context.user_data is not None and "create_alert_draft" in context.user_data:
        await message.reply_text(
            "Recebi seu áudio, mas o alerta em andamento precisa de respostas por texto. "
            "Seu rascunho continua salvo."
        )
        return
    if not _audio_transcription_available():
        await message.reply_text(
            "A transcrição de áudio não está habilitada nesta configuração. "
            "Envie sua solicitação por texto."
        )
        return
    duration = getattr(voice, "duration", None)
    if isinstance(duration, int) and duration > config.ASSISTANT_MAX_AUDIO_SECONDS:
        await message.reply_text(
            f"O áudio pode ter no máximo {config.ASSISTANT_MAX_AUDIO_SECONDS} segundos. "
            "Envie um trecho menor ou escreva sua solicitação."
        )
        return
    file_size = getattr(voice, "file_size", None)
    if isinstance(file_size, int) and file_size > config.ASSISTANT_MAX_AUDIO_BYTES:
        await message.reply_text("O arquivo de áudio é grande demais. Envie um áudio menor.")
        return
    if not await _reply_for_quota(
        message,
        context,
        user.id,
        audio=True,
        audio_seconds=duration if isinstance(duration, int) else 0,
    ):
        return
    try:
        if update.effective_chat:
            await update.effective_chat.send_action("record_voice")
    except Exception:
        pass

    text = await _audio_to_text(context, voice)
    if not text:
        await message.reply_text(
            "Não consegui transcrever seu áudio agora. Tente mandar por texto 🙂"
        )
        return
    await _handle_text(message, user.id, text, context, confirm_create=True)


async def assistant_create_confirm_cb(update: Update, context: CustomContext) -> None:
    query = update.callback_query
    user = update.effective_user
    if query is None or user is None:
        return
    match = ASS_CR_RE.match(query.data or "")
    if match is None:
        return
    action, token = match.groups()
    await query.answer()

    user_data = context.user_data
    pending = user_data.get("assistant_pending_alert") if user_data is not None else None
    if user_data is None or pending is None or pending.get("token") != token:
        await query.edit_message_text("Esta confirmação expirou. Envie o pedido novamente.")
        return

    if action == "no":
        user_data.pop("assistant_pending_alert", None)
        await query.edit_message_text("Certo, nenhum alerta foi criado.")
        return

    alert_name = pending.get("alert_name")
    municipality = pending.get("municipality")
    listing_kind = pending.get("listing_kind")
    neighbourhoods = pending.get("neighbourhoods")
    min_price = pending.get("min_price")
    max_price = pending.get("max_price")
    if (
        not alert_name
        or municipality not in MUNICIPALITIES
        or listing_kind not in {"aluguel", "venda"}
        or neighbourhoods is None
        or (min_price is None and max_price is None)
    ):
        user_data.pop("assistant_pending_alert", None)
        await query.edit_message_text("Esta confirmação expirou. Envie o pedido novamente.")
        return

    try:
        result = await data_create_alert(
            chat_id=user.id,
            alert_name=alert_name,
            min_price=min_price,
            max_price=max_price,
            neighbourhoods=neighbourhoods,
            listing_kind=cast(Literal["aluguel", "venda"], listing_kind),
            municipality=municipality,
            min_rooms=pending.get("min_rooms"),
            categories=pending.get("categories"),
        )
    except Exception:
        logger.exception("Falha ao criar alerta confirmado pelo assistente")
        await query.edit_message_text("Não consegui salvar agora. Tente confirmar novamente.")
        return

    user_data.pop("assistant_pending_alert", None)
    if result.status == "created":
        text = (
            f"✅ Alerta criado: <b>{html.escape(alert_name)}</b>. Você começa a receber os matches."
        )
    elif result.status == "reused":
        text = f"♻️ Você já tinha um alerta igual (<b>{html.escape(alert_name)}</b>). Nada criado."
    else:
        text = (
            "Você atingiu o limite de alertas do seu plano. Use /start pra ver "
            "as opções ou cadastre o e-mail pra ganhar Radar Pro."
        )
    await query.edit_message_text(text, parse_mode=ParseMode.HTML)


async def assistant_remove_confirm_cb(update: Update, context: CustomContext) -> None:
    query = update.callback_query
    user = update.effective_user
    if query is None or user is None:
        return
    data = query.data or ""
    await query.answer()

    if data == "ass_rm_no":
        try:
            await query.edit_message_text("Certo, nada foi removido.")
        except Exception:
            pass
        return

    m = ASS_RM_YES_RE.match(data)
    if m is None:
        return
    alert_id = int(m.group(1))
    try:
        outcome = await data_delete_alert(alert_id, user.id)
    except Exception:
        logger.exception("Falha ao remover alerta pelo assistente")
        await query.answer("Não deu pra remover. Tente de novo.", show_alert=True)
        return
    await query.edit_message_text(f"🗑️ {outcome.get('message', 'Alerta removido')}.")
    chat = update.effective_chat
    chat_id = chat.id if chat is not None else user.id
    remaining = await get_alerts_for_user(user.id)
    if remaining:
        await context.bot.send_message(
            chat_id=chat_id,
            text=_alerts_list_text(remaining),
            parse_mode=ParseMode.HTML,
        )
