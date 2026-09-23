"""
Textos centralizados do bot: boas-vindas, wizard, seeds e mensagens de erro.
"""

from __future__ import annotations

from datetime import datetime

from shared_models.tables import Alert
from shared_models.utils import format_brl
from telegram.helpers import escape_markdown

import config


def start_welcome() -> str:
    return "👋 *Olá!* Sou o bot de alertas OLX — *Maceió/AL*.\n\n"


def menu_principal_inline() -> str:
    return "🏠 *Menu principal*\nEscolha uma opção:"


def ajuda_comandos_plain() -> str:
    lines = [
        "Comandos\n"
        "/start — boas-vindas e menu principal\n"
        "/novo_alerta — criar alerta de aluguel ou compra\n"
        "/cancelar — sai do wizard de novo alerta\n"
    ]
    if config.BILLING_ENABLED:
        lines.append("/cancelar_pro — cancela a assinatura Radar Pro (Stars)\n")
    lines.append("/ajuda — esta mensagem")
    return "".join(lines)


def pro_price_label() -> str:
    return f"{config.PRO_STARS_AMOUNT} Stars/mês (≈ {config.PRO_PRICE_BRL_LABEL})"


def pro_upsell_hint() -> str:
    """Texto curto de upsell (Stars ou trial por e-mail)."""
    if config.BILLING_ENABLED:
        return pro_price_label()
    return (
        f"Cadastre seu e-mail e ganhe *{config.EMAIL_PRO_TRIAL_DAYS} dias* "
        "de Radar Pro grátis"
    )


def pro_pitch_message() -> str:
    if not config.BILLING_ENABLED:
        return (
            "🚀 *Radar Pro*\n\n"
            f"Até *{config.ALERT_PRO_CAP} alertas* e *{config.WATCHLIST_PRO_CAP} anúncios* "
            "acompanhados.\n\n"
            f"Cadastre seu e-mail e ganhe *1 mês* de Radar Pro grátis "
            f"({config.EMAIL_PRO_TRIAL_DAYS} dias).\n\n"
            "É só uma vez por conta — digite o e-mail quando pedir."
        )
    return (
        "🚀 *Radar Pro*\n\n"
        f"Até *{config.ALERT_PRO_CAP} alertas* e *{config.WATCHLIST_PRO_CAP} anúncios* "
        "acompanhados.\n\n"
        f"*{pro_price_label()}*\n"
        "Pagamento com Telegram Stars (moeda do app). "
        "O valor em reais é aproximado — o custo exato depende de como você compra Stars.\n\n"
        "Assinatura mensal; cancele quando quiser com /cancelar_pro."
    )


def pro_already_active() -> str:
    return "✅ Você já tem o *Radar Pro* ativo. Aproveite os limites maiores!"


def pro_activated() -> str:
    return (
        "✅ *Radar Pro ativado!*\n\n"
        f"Agora você pode ter até {config.ALERT_PRO_CAP} alertas e "
        f"{config.WATCHLIST_PRO_CAP} anúncios acompanhados."
    )


def pro_cancel_confirm() -> str:
    return (
        "Assinatura cancelada. O Pro continua até o fim do período já pago; "
        "depois você volta ao plano grátis."
    )


def pro_cancel_none() -> str:
    return "Você não tem uma assinatura Radar Pro ativa para cancelar."


def email_pro_trial_ask() -> str:
    return (
        "📧 *1 mês de Radar Pro grátis*\n\n"
        f"Envie seu e-mail para ativar *{config.EMAIL_PRO_TRIAL_DAYS} dias* "
        f"com até {config.ALERT_PRO_CAP} alertas e "
        f"{config.WATCHLIST_PRO_CAP} anúncios acompanhados.\n\n"
        "Ex.: `voce@email.com`\n"
        "Use /cancelar para desistir."
    )


def email_pro_trial_invalid() -> str:
    return (
        "Esse e-mail não parece válido. "
        "Envie de novo no formato `voce@email.com`."
    )


def email_pro_trial_email_taken() -> str:
    return (
        "Esse e-mail já foi usado em outra conta. "
        "Tente outro e-mail ou fale com o suporte."
    )


def email_pro_trial_already_claimed() -> str:
    return (
        "Você já resgatou o mês grátis do Radar Pro nesta conta. "
        "Quando o período acabar, o Pro pago volta a ficar disponível."
    )


def email_pro_trial_activated(*, pro_until: datetime | None) -> str:
    until_txt = ""
    if pro_until is not None:
        until = pro_until
        until_txt = f"\n\nVálido até *{until.day:02d}/{until.month:02d}/{until.year}*."
    return (
        "✅ *Radar Pro ativado por 1 mês!*\n\n"
        f"Agora você pode ter até {config.ALERT_PRO_CAP} alertas e "
        f"{config.WATCHLIST_PRO_CAP} anúncios acompanhados."
        f"{until_txt}"
    )


def email_pro_trial_canceled() -> str:
    return "Cadastro de e-mail cancelado. Você continua no plano grátis."


def email_pro_trial_error() -> str:
    return "Não consegui ativar o Pro agora. Tente de novo em instantes."


def alert_cap_reached(*, is_pro_user: bool = False) -> str:
    if is_pro_user:
        return (
            f"Você já tem {config.ALERT_PRO_CAP} alertas ativos "
            "(limite do Radar Pro).\n\n"
            "Remova um em *Meus Alertas* para criar outro."
        )
    return (
        f"Você já tem {config.ALERT_FREE_CAP} alerta ativo (limite grátis).\n\n"
        f"No *Radar Pro* você sobe para até {config.ALERT_PRO_CAP} alertas "
        f"— {pro_upsell_hint()}.\n\n"
        "Ou remova um alerta em *Meus Alertas* para criar outro no free."
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


def _rooms_label(min_rooms: int | None) -> str:
    if min_rooms is None:
        return "qualquer"
    return f"{min_rooms}+"


_CATEGORY_DISPLAY = {
    "Apartamentos": "Apartamento",
    "Casas": "Casa",
    "Aluguel de quartos": "Quarto",
}


def _categories_label(categories: list[str] | None) -> str:
    if not categories:
        return "qualquer"
    return ", ".join(_CATEGORY_DISPLAY.get(c, c) for c in categories)


def _meus_alertas_format_one(a: Alert) -> str:
    raw_name = a.alert_name or "Sem nome"
    name = escape_markdown(str(raw_name), version=1)
    status = "✅ Ativo" if a.active else "⏸ Pausado"
    kind_line = f"🏷️ *Tipo:* {_listing_kind_label(a.listing_kind)}"
    price_line = f"💰 *Preço:* {format_brl(a.min_price)} – {format_brl(a.max_price)}"
    rooms_line = f"🛏 *Quartos:* {_rooms_label(a.min_rooms)}"
    cats_line = f"🏠 *Categoria:* {_categories_label(a.categories)}"

    nh = a.neighbourhoods or []
    if nh:
        nh_joined = ", ".join(str(x) for x in nh)
        nh_str = escape_markdown(nh_joined, version=1)
        loc = f"📍 *Bairros:* {nh_str}"
    else:
        loc = "📍 *Bairros:* todos"

    esc_created = _meus_alertas_created_display(a.created_at)
    return (
        f"*{name}*\n{status}\n{kind_line}\n{price_line}\n{rooms_line}\n{cats_line}\n{loc}\n"
        f"📅 *Criado:* {esc_created}"
    )


def meus_alertas_detail_view(alert: Alert) -> str:
    raw_name = alert.alert_name or "Sem nome"
    name = escape_markdown(str(raw_name), version=1)
    status_line = "✅ Alerta ativo" if alert.active else "❌ Alerta inativo"
    kind_line = f"🏷️ {_listing_kind_label(alert.listing_kind)}"
    price_line = f"💰 {format_brl(alert.min_price)} – {format_brl(alert.max_price)}"
    rooms_line = f"🛏 {_rooms_label(alert.min_rooms)}"
    cats_line = f"🏠 {_categories_label(alert.categories)}"

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
        f"{rooms_line}\n"
        f"{cats_line}\n"
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
    """Fallback curto; lista vazia usa ``watchlist_empty_message``."""
    return "👀 *Anúncios acompanhados*"


def watchlist_carousel_header(*, count: int, cap: int) -> str:
    """Texto em que o loading se transforma quando o carrossel vai abaixo."""
    return f"👀 *Anúncios acompanhados* ({count}/{cap})"


def watchlist_erro() -> str:
    return (
        "👀 *Anúncios acompanhados*\n\n"
        "Não consegui carregar seus acompanhamentos agora. Tente de novo em instantes."
    )


def watchlist_empty_message(*, cap: int) -> str:
    return (
        f"👀 *Anúncios acompanhados* (0/{cap})\n\n"
        "Acompanhe anúncios pelo botão 👀 no carrossel de matches "
        "para receber aviso de mudança de preço ou status."
    )


def watchlist_sem_fotos(*, count: int, cap: int) -> str:
    return (
        f"👀 *Anúncios acompanhados* ({count}/{cap})\n\n"
        "Seus acompanhamentos estão salvos, mas nenhum tem foto para o carrossel agora."
    )


def watchlist_cap_reached(*, is_pro_user: bool = False) -> str:
    if is_pro_user:
        return (
            f"Você já acompanha {config.WATCHLIST_PRO_CAP} anúncios "
            "(limite do Radar Pro).\n\n"
            "Remova um em *Anúncios acompanhados* para liberar vaga."
        )
    return (
        f"Você já acompanha {config.WATCHLIST_FREE_CAP} anúncios "
        "(limite grátis).\n\n"
        f"No *Radar Pro* você sobe para até {config.WATCHLIST_PRO_CAP} "
        f"acompanhados e {config.ALERT_PRO_CAP} alertas "
        f"— {pro_upsell_hint()}.\n\n"
        "Ou remova um em *Anúncios acompanhados* para liberar vaga no free."
    )


def watchlist_cap_reached_alert(*, is_pro_user: bool = False) -> str:
    """Texto curto para ``show_alert`` (limite de caracteres do Telegram)."""
    if is_pro_user:
        return (
            f"Limite Pro de {config.WATCHLIST_PRO_CAP} anúncios atingido. "
            "Remova um para adicionar outro."
        )
    if config.BILLING_ENABLED:
        return (
            f"Limite grátis de {config.WATCHLIST_FREE_CAP} anúncios. "
            f"Radar Pro: até {config.WATCHLIST_PRO_CAP} "
            f"({config.PRO_STARS_AMOUNT} Stars/mês ≈ {config.PRO_PRICE_BRL_LABEL})."
        )
    return (
        f"Limite grátis de {config.WATCHLIST_FREE_CAP} anúncios. "
        "Cadastre o e-mail e ganhe 1 mês de Radar Pro."
    )


def watchlist_created_alert() -> str:
    return "Anúncio adicionado! Aviso se o preço mudar ou se sair do ar."


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
    fees = ""
    if listing_kind != "venda":
        fees = "\n\nCondomínio e IPTU entram na conta."
    return (
        f"💰 *Faixa de preço ({label})*\n\n"
        "Toque em uma opção ou *Personalizado*."
        f"{fees}"
    )


def wizard_quartos_intro() -> str:
    return "🛏 *Quartos*\n\nMínimo de quartos que você quer?"


def wizard_categorias_intro() -> str:
    return (
        "🏠 *Tipo de imóvel*\n\n"
        "Toque para selecionar (pode marcar mais de um). "
        "Sem seleção = qualquer tipo."
    )


def wizard_categorias_instrucao(selected: list[str]) -> str:
    if not selected:
        return "*Tipos selecionados:* nenhum ainda.\nToque para marcar ou conclua (qualquer)."
    labels = [_CATEGORY_DISPLAY.get(c, c) for c in selected]
    names = ", ".join(escape_markdown(n, version=1) for n in labels)
    return f"*Tipos selecionados:* {names}\nToque em mais ou conclua."


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


def price_range_label(min_price: int | None, max_price: int | None) -> str:
    if min_price is None:
        return f"Até {format_brl(max_price)}"
    if max_price is None:
        return f"A partir de {format_brl(min_price)}"
    return f"{format_brl(min_price)} – {format_brl(max_price)}"


def wizard_tipo_escolhido(*, listing_kind: str) -> str:
    return f"🏷️ *Tipo:* {_listing_kind_label(listing_kind)}"


def wizard_preco_escolhido(
    *,
    listing_kind: str,
    min_price: int | None,
    max_price: int | None,
) -> str:
    kind_label = "compra" if listing_kind == "venda" else "aluguel"
    price = escape_markdown(price_range_label(min_price, max_price), version=1)
    return f"💰 *Faixa de preço ({kind_label}):* {price}"


def wizard_preco_personalizado(*, listing_kind: str) -> str:
    kind_label = "compra" if listing_kind == "venda" else "aluguel"
    return f"💰 *Faixa de preço ({kind_label}):* personalizado"


def wizard_quartos_escolhido(min_rooms: int | None) -> str:
    rooms = escape_markdown(_rooms_label(min_rooms), version=1)
    return f"🛏 *Quartos:* {rooms}"


def wizard_categorias_escolhido(selected: list[str] | None) -> str:
    label = escape_markdown(_categories_label(selected), version=1)
    return f"🏠 *Tipo de imóvel:* {label}"


def wizard_bairros_escolhido(selected: list[str]) -> str:
    if not selected:
        names = "Qualquer bairro"
    else:
        names = ", ".join(sorted(selected))
    return f"📍 *Bairros:* {escape_markdown(names, version=1)}"


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


def db_loading() -> str:
    """Loading explícito enquanto o Postgres (Neon) acorda / responde."""
    return (
        "⏳ *Carregando…*\n\n"
        "Isso pode levar alguns segundos."
    )


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
    min_rooms: int | None = None,
    categories: list[str] | None = None,
) -> str:
    esc_price = escape_markdown(price_s, version=1)
    esc_nb = escape_markdown(nb_s, version=1)
    esc_name = escape_markdown(name, version=1)
    esc_rooms = escape_markdown(_rooms_label(min_rooms), version=1)
    esc_cats = escape_markdown(_categories_label(categories), version=1)
    kind_label = _listing_kind_label(listing_kind)
    return (
        "🧾 *Confirmação do alerta*\n\n"
        f"🏷️ *Tipo:* {kind_label}\n"
        f"💰 *Preço:* {esc_price}\n"
        f"🛏 *Quartos:* {esc_rooms}\n"
        f"🏠 *Categoria:* {esc_cats}\n"
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