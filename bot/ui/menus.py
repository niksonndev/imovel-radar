"""
Textos centralizados do bot: boas-vindas, wizard, seeds e mensagens de erro.

Funções puras que retornam ``str`` (muitas em Markdown). Os handlers montam a
resposta com ``parse_mode`` adequado; aqui só fica o conteúdo para facilitar
ajuste de copy e tradução sem espalhar strings nos handlers.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from telegram.helpers import escape_markdown

from utils.pricing import format_brl


def start_welcome() -> str:
    return "👋 *Olá!* Sou o bot de alertas OLX — *Maceió/AL*.\n\n"


def menu_principal_inline() -> str:
    return "🏠 *Menu principal*\nEscolha uma opção:"


def ajuda_comandos_plain() -> str:
    return (
        "Comandos\n"
        "/start — boas-vindas e menu principal\n"
        "/novo_alerta — criar alerta de aluguel\n"
        "/ajuda — esta mensagem"
    )


def meus_alertas_erro() -> str:
    return (
        "📋 *Meus Alertas*\n\n"
        "Não consegui carregar seus alertas agora. Tente de novo em instantes."
    )


def _meus_alertas_created_display(raw: object) -> str:
    """Converte ``created_at`` ISO do SQLite para *dd/mm/aaaa*."""
    s = str(raw or "").strip()
    if not s:
        return "—"
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        formatted = f"{dt.day:02d}/{dt.month:02d}/{dt.year}"
    except ValueError:
        formatted = s
    return escape_markdown(formatted, version=1)


def _meus_alertas_format_one(a: dict[str, Any]) -> str:
    raw_name = a.get("alert_name") or "Sem nome"
    name = escape_markdown(str(raw_name), version=1)
    active = int(a.get("active") or 0)
    status = "✅ Ativo" if active else "⏸ Pausado"

    pmin, pmax = a.get("min_price"), a.get("max_price")
    if pmin is None and pmax is None:
        price_line = "💰 *Preço:* qualquer faixa"
    else:
        price_line = f"💰 *Preço:* {format_brl(pmin)} – {format_brl(pmax)}"

    nh_raw = a.get("neighbourhoods") or "[]"
    try:
        nh = json.loads(nh_raw) if isinstance(nh_raw, str) else nh_raw
    except json.JSONDecodeError:
        nh = []
    if isinstance(nh, list) and nh:
        nh_joined = ", ".join(str(x) for x in nh)
        nh_str = escape_markdown(nh_joined, version=1)
        loc = f"📍 *Bairros:* {nh_str}"
    else:
        loc = "📍 *Bairros:* todos"

    esc_created = _meus_alertas_created_display(a.get("created_at"))
    return f"*{name}*\n{status}\n{price_line}\n{loc}\n📅 *Criado:* {esc_created}"


def meus_alertas_detail_view(alert: dict[str, Any]) -> str:
    """Texto compacto de um alerta (tela de detalhe antes de editar/remover)."""
    raw_name = alert.get("alert_name") or "Sem nome"
    name = escape_markdown(str(raw_name), version=1)
    active = int(alert.get("active") or 0)
    status_line = "✅ Alerta ativo" if active else "❌ Alerta inativo"

    pmin, pmax = alert.get("min_price"), alert.get("max_price")
    if pmin is None and pmax is None:
        price_line = "💰 Qualquer faixa"
    else:
        price_line = f"💰 {format_brl(pmin)} – {format_brl(pmax)}"

    nh_raw = alert.get("neighbourhoods") or "[]"
    try:
        nh = json.loads(nh_raw) if isinstance(nh_raw, str) else nh_raw
    except json.JSONDecodeError:
        nh = []
    if isinstance(nh, list) and nh:
        loc_short = ", ".join(str(x) for x in nh)
    else:
        loc_short = "Todos"
    loc_esc = escape_markdown(loc_short, version=1)
    bairros_line = f"📍 {loc_esc}"

    esc_created = _meus_alertas_created_display(alert.get("created_at"))
    return (
        "📋 *Meus Alertas*\n\n"
        f"*{name}*\n"
        f"{status_line}\n"
        f"{price_line}\n"
        f"{bairros_line}\n"
        f"📅 *Criado:* {esc_created}"
    )


def meus_alertas_editar_stub(alert: dict[str, Any]) -> str:
    """Mensagem temporária até o wizard de edição existir."""
    raw_name = alert.get("alert_name") or "Sem nome"
    esc = escape_markdown(str(raw_name), version=1)
    return (
        "✏️ *Editar alerta*\n\n"
        f"*{esc}*\n\n"
        "A edição completa pelo bot ainda não está disponível. "
        "Você pode *remover* este alerta e criar outro com `/novo_alerta`."
    )


def meus_alertas_list_message(
    alerts: list[dict[str, Any]],
) -> tuple[str, list[dict[str, Any]]]:
    """
    Texto da listagem e sublista de alertas realmente incluídos no texto
    (para montar botões de escolha alinhados ao que aparece na mensagem).
    """
    header = "📋 *Meus Alertas*\n\n"
    if not alerts:
        return (
            header
            + "Você ainda não tem alertas. Use `/novo_alerta` para criar o primeiro.",
            [],
        )

    hint = "_Toque no nome de um alerta abaixo para editar ou excluir._\n\n"
    blocks = [_meus_alertas_format_one(a) for a in alerts]
    max_len = 4080
    visible_count = len(blocks)
    while visible_count > 0:
        body_blocks = blocks[:visible_count]
        body = "\n\n".join(body_blocks)
        full = header + hint + body
        omitted = len(alerts) - visible_count
        suffix = ""
        if omitted > 0:
            suffix = (
                f"\n\n_… e mais {omitted} alerta(s) (limite de tamanho da mensagem)._"
            )
        if len(full) + len(suffix) <= max_len:
            visible = alerts[:visible_count]
            return full + suffix, visible
        visible_count -= 1
    return (
        header + hint + "Não coube listar os alertas nesta mensagem. Tente /ajuda.",
        [],
    )


def meus_alertas_view(alerts: list[dict[str, Any]]) -> str:
    """Compat: só o texto da listagem (sem separar alertas visíveis)."""
    text, _ = meus_alertas_list_message(alerts)
    return text


def menu_watchlist() -> str:
    return "👀 *Acompanhar anúncio*\n\nEsta área ainda está em construção."


# —— Wizard novo alerta ——


def wizard_novo_alerta_intro() -> str:
    return (
        "🆕 *Novo alerta (aluguel)*\n\n"
        "Faixa de preço — toque em uma opção ou *Personalizado*."
    )


def wizard_sessao_expirada() -> str:
    return "Sua sessão do wizard expirou. Use /novo_alerta novamente."


def wizard_sessao_expirada_curta() -> str:
    return "Sessão expirada. Use /novo_alerta novamente."


def wizard_personalizado_min() -> str:
    return "Personalizado: envie o *preço mínimo* (R$, só número)."


def wizard_bairros_instrucao(selected: list[str]) -> str:
    """
    Corpo Markdown (v1) da mensagem do passo *bairros* no /novo_alerta.
    Nomes vêm do banco; escapados para evitar quebra de *Markdown*.
    """
    if not selected:
        return (
            "*Bairros selecionados:* nenhum ainda.\nToque em mais bairros ou conclua."
        )
    names = ", ".join(escape_markdown(n, version=1) for n in sorted(selected))
    return f"*Bairros selecionados:* {names}\nToque em mais bairros ou conclua."


def wizard_nome_invalido() -> str:
    return "Nome inválido. Tente de novo."


def wizard_preco_min_invalido() -> str:
    return "Número inválido. Ex.: 150000"


def wizard_preco_max_invalido() -> str:
    return "Número inválido."


def wizard_preco_max_menor_min() -> str:
    return "O preço máximo deve ser maior ou igual ao mínimo."


def wizard_preco_max_prompt() -> str:
    return "Preço *máximo* (R$):"


def wizard_nome_prompt() -> str:
    return "Agora, envie o *nome do alerta* (ex.: `Aluguel Centro`)."


def wizard_nome_ausente() -> str:
    return "Nome do alerta ausente. Tente novamente pelo menu principal."


def wizard_salvar_falha() -> str:
    return "Não consegui salvar seu alerta agora. Tente novamente em instantes."


def wizard_nao_salvo() -> str:
    return "Ok! O alerta não foi salvo."


def wizard_seed_loading() -> str:
    return "⏳ Peraê, tô procurando imóveis pra você..."


def wizard_cancelado() -> str:
    return "Criação de alerta cancelada."


def confirmacao_resumo(*, price_s: str, nb_s: str, name: str) -> str:
    esc_price = escape_markdown(price_s, version=1)
    esc_nb = escape_markdown(nb_s, version=1)
    esc_name = escape_markdown(name, version=1)
    return (
        "🧾 *Confirmação do alerta*\n\n"
        f"💰 *Preço:* {esc_price}\n"
        f"📍 *Bairros:* {esc_nb}\n"
        f"📝 *Nome:* `{esc_name}`\n\n"
        "Confirme abaixo:"
    )


def seed_sem_cache() -> str:
    return (
        "⚠️ Não consegui consultar o cache de imóveis agora. "
        "Vou tentar na próxima verificação automática. 🔔"
    )


def seed_nenhum_imovel() -> str:
    return (
        "🔍 Nenhum imóvel encontrado com esses filtros no momento.\n"
        "Vou te avisar quando aparecer algo novo. 🔔"
    )


def seed_alert_created() -> str:
    return "✅ Alerta criado! Vou te avisar quando aparecer algo novo. 🔔"
