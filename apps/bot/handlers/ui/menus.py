"""
Textos centralizados do bot: boas-vindas, wizard, seeds e mensagens de erro.
"""

from __future__ import annotations

import json
from datetime import datetime

from shared_models import Alert
from shared_models.utils import format_brl
from telegram.helpers import escape_markdown


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
    s = str(raw or "").strip()
    if not s:
        return "—"
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        formatted = f"{dt.day:02d}/{dt.month:02d}/{dt.year}"
    except ValueError:
        formatted = s
    return escape_markdown(formatted, version=1)


def _meus_alertas_format_one(a: Alert) -> str:
    raw_name = a.alert_name or "Sem nome"
    name = escape_markdown(str(raw_name), version=1)
    status = "✅ Ativo" if a.active else "⏸ Pausado"
    price_line = f"💰 *Preço:* {format_brl(a.min_price)} – {format_brl(a.max_price)}"

    nh_raw = a.neighbourhoods or "[]"
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

    esc_created = _meus_alertas_created_display(a.created_at)
    return f"*{name}*\n{status}\n{price_line}\n{loc}\n📅 *Criado:* {esc_created}"


def meus_alertas_detail_view(alert: Alert) -> str:
    raw_name = alert.alert_name or "Sem nome"
    name = escape_markdown(str(raw_name), version=1)
    status_line = "✅ Alerta ativo" if alert.active else "❌ Alerta inativo"
    price_line = f"💰 {format_brl(alert.min_price)} – {format_brl(alert.max_price)}"

    nh_raw = alert.neighbourhoods or "[]"
    try:
        nh = json.loads(nh_raw) if isinstance(nh_raw, str) else nh_raw
    except json.JSONDecodeError:
        nh = []
    loc_short = ", ".join(str(x) for x in nh) if isinstance(nh, list) and nh else "Todos"
    loc_esc = escape_markdown(loc_short, version=1)
    bairros_line = f"📍 {loc_esc}"

    esc_created = _meus_alertas_created_display(alert.created_at)
    return (
        "📋 *Meus Alertas*\n\n"
        f"*{name}*\n"
        f"{status_line}\n"
        f"{price_line}\n"
        f"{bairros_line}\n"
        f"📅 *Criado:* {esc_created}"
    )


def meus_alertas_editar_stub(alert: Alert) -> str:
    raw_name = alert.alert_name or "Sem nome"
    esc = escape_markdown(str(raw_name), version=1)
    return (
        "✏️ *Editar alerta*\n\n"
        f"*{esc}*\n\n"
        "A edição completa pelo bot ainda não está disponível. "
        "Você pode *remover* este alerta e criar outro com `/novo_alerta`."
    )


def meus_alertas_list_message(alerts: list[Alert]) -> tuple[str, list[Alert]]:
    header = "📋 *Meus Alertas*\n\n"
    if not alerts:
        return (
            header + "Você ainda não tem alertas. Use `/novo_alerta` para criar o primeiro.",
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
            suffix = f"\n\n_… e mais {omitted} alerta(s) (limite de tamanho da mensagem)._"
        if len(full) + len(suffix) <= max_len:
            visible = alerts[:visible_count]
            return full + suffix, visible
        visible_count -= 1
    return (
        header + hint + "Não coube listar os alertas nesta mensagem. Tente /ajuda.",
        [],
    )


def meus_alertas_view(alerts: list[Alert]) -> str:
    text, _ = meus_alertas_list_message(alerts)
    return text


def menu_watchlist() -> str:
    return "👀 *Acompanhar anúncio*\n\nEsta área ainda está em construção."


# —— Wizard novo alerta ——


def wizard_novo_alerta_intro() -> str:
    return "🆕 *Novo alerta (aluguel)*\n\nFaixa de preço — toque em uma opção ou *Personalizado*."


def wizard_sessao_expirada() -> str:
    return "Sua sessão do wizard expirou. Use /novo_alerta novamente."


def wizard_sessao_expirada_curta() -> str:
    return "Sessão expirada. Use /novo_alerta novamente."


def wizard_personalizado_min() -> str:
    return "Personalizado: envie o *preço mínimo* (R$, só número)."


def wizard_bairros_instrucao(selected: list[str]) -> str:
    if not selected:
        return "*Bairros selecionados:* nenhum ainda.\nToque em mais bairros ou conclua."
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