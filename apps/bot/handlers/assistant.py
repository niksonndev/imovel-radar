"""
Assistente de linguagem natural fora do wizard (Fase 1+2).

Um ``MessageHandler`` de texto livre que decide (via roteador de intenção) qual
ferramenta acionar: listar/remover/criar alertas e consultar o mercado. Ações
destrutivas (remover) exigem confirmação inline.

Roteamento: ``infrastructure/ai/assistant_intent.extract_assistant_intent``.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from dataclasses import dataclass
from typing import TYPE_CHECKING

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
)
from handlers.nl_intent import auto_alert_name
from infrastructure.ai import alert_extractor
from infrastructure.ai.assistant_intent import (
    MUNICIPALITIES,
    AssistantIntent,
    extract_assistant_intent,
)
from models import CustomContext

if TYPE_CHECKING:
    from shared_models.tables import Alert

logger = logging.getLogger(__name__)

ASS_RM_YES_RE = re.compile(r"^ass_rm_yes_(\d+)$")


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


async def _tool_consultar_mercado(intent: AssistantIntent) -> AssistantReply:
    snapshot = await get_latest_market_snapshot()
    if not snapshot:
        return AssistantReply(
            "Ainda não tenho a coleta de mercado mais recente. Tente de novo mais tarde."
        )

    municipality = intent.municipality or "Maceió"
    kind = intent.listing_kind or "aluguel"
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
            if chosen is not None and chosen.get("ranked") and chosen.get("mean_price") is not None:
                out = (
                    f"Média de {kind} em <b>{chosen['name']}</b> ({municipality}): "
                    f"<b>{_format_brl(chosen['mean_price'])}</b>"
                )
                if kind == "aluguel":
                    out += f" · {chosen.get('sample')} anúncios na amostra"
                return AssistantReply(out)
        return AssistantReply(f"Sem amostra confiável de {nb_raw.title()} em {municipality}.")

    out = f"Média de {kind} em {municipality}: <b>{_format_brl(stats.get('mean_price'))}</b>"
    if kind == "aluguel" and stats.get("mean_rent_plus_condo") is not None:
        out += f" · com condomínio: <b>{_format_brl(stats['mean_rent_plus_condo'])}</b>"
    out += f" · {stats.get('sample')} anúncios na amostra"
    return AssistantReply(out)


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


async def _tool_criar(chat_id: int, text: str) -> AssistantReply:
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
    return AssistantReply(
        "Como posso ajudar? Posso:\n"
        "• listar seus alertas\n"
        "• remover um alerta (ex.: <b>remove o alerta de Ponta Verde</b>)\n"
        "• criar um alerta (ex.: <b>quero apto em Jatiúca até R$ 2.500</b>)\n"
        "• consultar o mercado (ex.: <b>média de aluguel em Boa Viagem?</b>)\n"
        "\nE também aceito <b>mensagens de voz</b> — me manda um áudio com o que você precisa 🙂\n"
    )


# ── Dispatcher ─────────────────────────────────────────────────────────────
async def _handle_text(message, user_id: int, text: str) -> None:
    """Extrai a intenção e responde (compartilhado por texto e áudio)."""
    intent = await extract_assistant_intent(
        text,
        provider=config.LLM_PROVIDER,
        api_key=config.resolve_openai_api_key(),
        model=config.LLM_MODEL,
        timeout_s=config.LLM_TIMEOUT_SECONDS,
    )
    try:
        if intent.tool == "remover_alertas":
            reply = await _tool_remover(user_id, intent)
        elif intent.tool == "listar_alertas":
            reply = await _tool_listar(user_id)
        elif intent.tool == "consultar_mercado":
            reply = await _tool_consultar_mercado(intent)
        elif intent.tool == "criar_alerta":
            reply = await _tool_criar(user_id, text)
        elif intent.tool == "ajuda":
            reply = _tool_ajuda()
        else:
            reply = AssistantReply(
                "Sou o assistente do Imóvel Radar. Posso listar, remover e criar alertas, "
                "além de consultar o mercado. Diga o que precisa 🙂"
            )
    except Exception:
        logger.exception("Erro no assistente (intent=%s)", intent.tool)
        reply = AssistantReply("Ops, deu um erro processando isso. Tente de novo.")

    await message.reply_text(
        reply.text,
        parse_mode=ParseMode.HTML,
        reply_markup=reply.markup,
    )


async def assistant_message(update: Update, context: CustomContext) -> None:
    message = update.effective_message
    user = update.effective_user
    if message is None or user is None:
        return
    text = (message.text or "").strip()
    if not text:
        return
    await _handle_text(message, user.id, text)


async def _audio_to_text(context: CustomContext, file_id: str) -> str | None:
    """Baixa o áudio do Telegram e transcreve via Whisper."""
    from infrastructure.ai.transcription import transcribe_audio

    api_key = config.resolve_openai_api_key()
    if config.LLM_PROVIDER != "openai" or not api_key:
        return None
    file = await context.bot.get_file(file_id)
    raw = await file.download_as_bytearray()
    text = await transcribe_audio(
        bytes(raw),
        api_key=api_key,
        filename="audio",  # extensão inferida pelo Telegram no MIME
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
    try:
        if update.effective_chat:
            await update.effective_chat.send_action("record_voice")
    except Exception:
        pass

    text = await _audio_to_text(context, voice.file_id)
    if not text:
        await message.reply_text(
            "Não consegui transcrever seu áudio agora. Tente mandar por texto 🙂"
        )
        return
    await _handle_text(message, user.id, text)


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
