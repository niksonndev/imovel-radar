"""
Textos centralizados do bot: boas-vindas, wizard, seeds e mensagens de erro.
"""

from __future__ import annotations

from datetime import datetime

from shared_models.tables import Alert, WatchedListingChange
from shared_models.utils import format_brl
from telegram.helpers import escape_markdown

import config


def start_welcome() -> str:
    return "👋 *Olá!* Sou o bot de alertas OLX — *Maceió/AL*.\n\n"


def menu_principal_inline() -> str:
    return "🏠 *Menu principal*\nEscolha uma opção:"


def ajuda_comandos_plain() -> str:
    return (
        "Comandos\n"
        "/start — boas-vindas e menu principal\n"
        "/novo_alerta — criar alerta de aluguel ou compra\n"
        "/cancelar — sai do wizard de novo alerta ou de acompanhar anúncio\n"
        "/ajuda — esta mensagem"
    )


def meus_alertas_erro() -> str:
    return (
        "📋 *Meus Alertas*\n\n"
        "Não consegui carregar seus alertas agora. Tente de novo em instantes."
    )


def _meus_alertas_created_display(created_at: datetime | None) -> str:
    if created_at is None:
        return "—"
    formatted = f"{created_at.day:02d}/{created_at.month:02d}/{created_at.year}"
    return escape_markdown(formatted, version=1)


def _listing_kind_label(kind: str | None) -> str:
    return "Comprar" if kind == "venda" else "Alugar"


def _meus_alertas_format_one(a: Alert) -> str:
    raw_name = a.alert_name or "Sem nome"
    name = escape_markdown(str(raw_name), version=1)
    status = "✅ Ativo" if a.active else "⏸ Pausado"
    kind_line = f"🏷️ *Tipo:* {_listing_kind_label(a.listing_kind)}"
    price_line = f"💰 *Preço:* {format_brl(a.min_price)} – {format_brl(a.max_price)}"

    nh = a.neighbourhoods or []
    if nh:
        nh_joined = ", ".join(str(x) for x in nh)
        nh_str = escape_markdown(nh_joined, version=1)
        loc = f"📍 *Bairros:* {nh_str}"
    else:
        loc = "📍 *Bairros:* todos"

    esc_created = _meus_alertas_created_display(a.created_at)
    return f"*{name}*\n{status}\n{kind_line}\n{price_line}\n{loc}\n📅 *Criado:* {esc_created}"


def meus_alertas_detail_view(alert: Alert) -> str:
    raw_name = alert.alert_name or "Sem nome"
    name = escape_markdown(str(raw_name), version=1)
    status_line = "✅ Alerta ativo" if alert.active else "❌ Alerta inativo"
    kind_line = f"🏷️ {_listing_kind_label(alert.listing_kind)}"
    price_line = f"💰 {format_brl(alert.min_price)} – {format_brl(alert.max_price)}"

    nh = alert.neighbourhoods or []
    loc_short = ", ".join(str(x) for x in nh) if nh else "Todos"
    loc_esc = escape_markdown(loc_short, version=1)
    bairros_line = f"📍 {loc_esc}"

    esc_created = _meus_alertas_created_display(alert.created_at)
    return (
        "📋 *Meus Alertas*\n\n"
        f"*{name}*\n"
        f"{status_line}\n"
        f"{kind_line}\n"
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
    """Fallback curto; a listagem real usa ``watchlist_list_message``."""
    return "👀 *Acompanhar anúncio*"


def watchlist_erro() -> str:
    return (
        "👀 *Acompanhar anúncio*\n\n"
        "Não consegui carregar seus acompanhamentos agora. Tente de novo em instantes."
    )


def _watchlist_format_one(row: WatchedListingChange) -> str:
    listing = row.listing
    title = escape_markdown(str(listing.title or "Sem título")[:80], version=1)
    price = format_brl(listing.price_value)
    nh = escape_markdown(str(listing.neighbourhood or "—"), version=1)
    status = "✅ No ar" if listing.active else "❌ Fora do ar"
    return f"*{title}*\n💰 {price} · 📍 {nh}\n{status}"


def watchlist_list_message(
    rows: list[WatchedListingChange],
) -> tuple[str, list[WatchedListingChange]]:
    cap = config.WATCHLIST_FREE_CAP
    header = f"👀 *Acompanhar anúncio* ({len(rows)}/{cap})\n\n"
    if not rows:
        return (
            header
            + "Cole o link de um anúncio do OLX para acompanhar preço e status.\n"
            "Também dá para acompanhar direto pelo carrossel de matches.",
            [],
        )

    hint = "_Toque num anúncio abaixo para ver detalhes ou parar de acompanhar._\n\n"
    blocks = [_watchlist_format_one(r) for r in rows]
    max_len = 4080
    visible_count = len(blocks)
    while visible_count > 0:
        body = "\n\n".join(blocks[:visible_count])
        full = header + hint + body
        omitted = len(rows) - visible_count
        suffix = ""
        if omitted > 0:
            suffix = f"\n\n_… e mais {omitted} anúncio(s)._"
        if len(full) + len(suffix) <= max_len:
            return full + suffix, rows[:visible_count]
        visible_count -= 1
    return header + hint + "Não coube listar nesta mensagem.", []


def watchlist_detail_view(row: WatchedListingChange) -> str:
    listing = row.listing
    title = escape_markdown(str(listing.title or "Sem título"), version=1)
    price = format_brl(listing.price_value)
    nh = escape_markdown(str(listing.neighbourhood or "—"), version=1)
    status = "✅ No ar" if listing.active else "❌ Fora do ar"
    url = listing.url or ""
    url_line = f"\n🔗 {escape_markdown(url, version=1)}" if url else ""
    return (
        "👀 *Anúncio acompanhado*\n\n"
        f"*{title}*\n"
        f"💰 {price}\n"
        f"📍 {nh}\n"
        f"{status}"
        f"{url_line}"
    )


def watchlist_url_prompt() -> str:
    return (
        "👀 *Adicionar anúncio*\n\n"
        "Cole o link do anúncio no OLX (ex.: `https://al.olx.com.br/...-1525220692`).\n\n"
        "O anúncio precisa já estar no nosso radar (coleta diária)."
    )


def watchlist_url_invalida() -> str:
    return "Link inválido. Envie a URL completa do anúncio no OLX."


def watchlist_listing_missing() -> str:
    return (
        "Esse anúncio ainda não está no nosso radar. "
        "Ele entra após a coleta diária — tente de novo amanhã."
    )


def watchlist_cap_reached() -> str:
    cap = config.WATCHLIST_FREE_CAP
    return (
        f"Você já acompanha {cap} anúncios (limite grátis). "
        "Remova um para adicionar outro."
    )


def watchlist_duplicate() -> str:
    return "Você já acompanha este anúncio."


def watchlist_confirm_resumo(
    *,
    title: str,
    price_value: int | None,
    neighbourhood: str,
) -> str:
    esc_title = escape_markdown(title[:80], version=1)
    esc_nh = escape_markdown(neighbourhood or "—", version=1)
    return (
        "🧾 *Confirmar acompanhamento*\n\n"
        f"*{esc_title}*\n"
        f"💰 {format_brl(price_value)}\n"
        f"📍 {esc_nh}\n\n"
        "Vou avisar se o preço mudar ou se o anúncio sair do ar."
    )


def watchlist_created() -> str:
    return "✅ Anúncio adicionado! Aviso você se o preço mudar ou se sair do ar."


def watchlist_cancelado() -> str:
    return "Ok, não adicionei o anúncio."


def watchlist_change_price_message(
    *,
    title: str,
    old_price: int | None,
    new_price: int | None,
    url: str | None,
) -> str:
    esc_title = escape_markdown(title[:80], version=1)
    body = (
        "👀 *Mudança de preço*\n\n"
        f"*{esc_title}*\n"
        f"💰 {format_brl(old_price)} → {format_brl(new_price)}"
    )
    if url:
        body += f"\n🔗 {escape_markdown(url, version=1)}"
    return body


def watchlist_change_removed_message(*, title: str, url: str | None) -> str:
    esc_title = escape_markdown(title[:80], version=1)
    body = (
        "👀 *Anúncio fora do ar*\n\n"
        f"*{esc_title}*\n"
        "Esse anúncio saiu do radar (provavelmente removido ou vendido)."
    )
    if url:
        body += f"\n🔗 {escape_markdown(url, version=1)}"
    return body


def watchlist_change_reactivated_message(*, title: str, url: str | None) -> str:
    esc_title = escape_markdown(title[:80], version=1)
    body = (
        "👀 *Anúncio de volta*\n\n"
        f"*{esc_title}*\n"
        "Esse anúncio voltou a aparecer no radar."
    )
    if url:
        body += f"\n🔗 {escape_markdown(url, version=1)}"
    return body


# —— Wizard novo alerta ——


def wizard_novo_alerta_intro() -> str:
    return "🆕 *Novo alerta*\n\nO que você procura?"


def wizard_preco_intro(*, listing_kind: str) -> str:
    label = "compra" if listing_kind == "venda" else "aluguel"
    return (
        f"💰 *Faixa de preço ({label})*\n\n"
        "Toque em uma opção ou *Personalizado*."
    )


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


def confirmacao_resumo(
    *,
    price_s: str,
    nb_s: str,
    name: str,
    listing_kind: str = "aluguel",
) -> str:
    esc_price = escape_markdown(price_s, version=1)
    esc_nb = escape_markdown(nb_s, version=1)
    esc_name = escape_markdown(name, version=1)
    kind_label = _listing_kind_label(listing_kind)
    return (
        "🧾 *Confirmação do alerta*\n\n"
        f"🏷️ *Tipo:* {kind_label}\n"
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


def seed_alert_already_exists() -> str:
    return (
        "ℹ️ Você já tem um alerta com esses filtros.\n"
        "Nenhum imóvel novo desde a última notificação. 🔔"
    )


def seed_alert_created() -> str:
    return "✅ Alerta criado! Vou te avisar quando aparecer algo novo. 🔔"


def seed_alert_new_matches() -> str:
    return "✅ Encontrei imóveis novos para o seu alerta! 🔔"