"""Textos de tela e mensagens do bot (comandos, menus, wizard)."""

from __future__ import annotations


def start_welcome() -> str:
    return "👋 *Olá!* Sou o bot de alertas OLX — *Maceió/AL*.\n\n"


def meus_alertas_unavailable() -> str:
    return "📋 Meus alertas está temporariamente indisponível. Tente novamente em instantes."


def meus_alertas_unavailable_inline() -> str:
    return "📋 Meus alertas está temporariamente indisponível no momento."


def pausar_unavailable() -> str:
    return "⏸️ Pausar/reativar alerta está temporariamente indisponível."


def deletar_unavailable() -> str:
    return "🗑️ Deletar alerta está temporariamente indisponível."


def observar_unavailable() -> str:
    return "`/observar` por URL está temporariamente indisponível."


def watchlist_unavailable() -> str:
    return "👀 Watchlist está temporariamente indisponível. Tente novamente em instantes."


def watchlist_unavailable_inline() -> str:
    return "👀 Watchlist está temporariamente indisponível no momento."


def remover_unavailable() -> str:
    return "🧹 Remover da watchlist está temporariamente indisponível."


def status_command(*, watch_days: int, next_alert: str, next_watch: str) -> str:
    return (
        f"*Status*\n"
        f"• Scrape/alertas: diariamente às *03:00* (Maceió) (próx.: _{next_alert}_)\n"
        f"• Watchlist: a cada *{watch_days}* dia(s) (próx.: _{next_watch}_)\n"
        f"• Região: Maceió/AL"
    )


def status_menu(*, watch_days: int, next_alert: str, next_watch: str) -> str:
    return (
        f"*Status*\n"
        f"• Scrape/alertas: diariamente às *05:00* (Maceió) (próx.: _{next_alert}_)\n"
        f"• Watchlist: a cada *{watch_days}* dia(s) (próx.: _{next_watch}_)\n"
        f"• Região: Maceió/AL"
    )


def ajuda_comandos() -> str:
    return (
        "*Comandos*\n"
        "/start — boas-vindas\n"
        "/novo_alerta — criar alerta de aluguel (preço, bairros, nome)\n"
        "/meus_alertas — listar alertas (id, nome, ativo/pausado)\n"
        "/pausar_alerta [id] — pausar ou reativar\n"
        "/deletar_alerta [id] — apagar alerta\n"
        "/observar [url OLX] — monitorar preço do anúncio\n"
        "/watchlist — listar observados\n"
        "/remover [id] — tirar da watchlist\n"
        "/status — intervalos e próximas execuções\n"
        "/cancelar — cancelar wizard\n\n"
        "Alertas disparam quando aparece anúncio novo nos filtros. "
        "Watchlist avisa mudança de preço ou remoção."
    )


def ajuda_menu_inline() -> str:
    return (
        "*Como usar sem digitar comandos*\n\n"
        "Use os botões do menu principal para criar e gerenciar alertas, "
        "acompanhar anúncios, abrir watchlist e ver status.\n\n"
        "Você pode voltar ao menu principal pelos botões em cada tela."
    )


def menu_principal_inline() -> str:
    return "🏠 *Menu principal*\nEscolha uma opção:"


def alert_toggle_unavailable() -> str:
    return "⏸️ Ação de pausar/reativar está temporariamente indisponível."


def alert_delete_unavailable() -> str:
    return "🗑️ Ação de deletar alerta está temporariamente indisponível."


def watch_remove_unavailable() -> str:
    return "🧹 Ação de remover da watchlist está temporariamente indisponível."


def id_alerta_invalido() -> str:
    return "ID de alerta inválido. Confira e tente novamente."


def id_watchlist_invalido() -> str:
    return "ID da watchlist inválido. Confira e tente novamente."


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


def wizard_selecione_bairros() -> str:
    return "Selecione os *bairros* (toque para marcar). Depois: Concluir."


def wizard_selecione_bairros_com_obs() -> str:
    return (
        "Selecione os *bairros* (toque para marcar). Depois: Concluir.\n"
        "Se não quiser filtrar por bairro, conclua sem marcar."
    )


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
    return (
        "🧾 *Confirmação do alerta*\n\n"
        f"💰 *Preço:* {price_s}\n"
        f"📍 *Bairros:* {nb_s}\n"
        f"📝 *Nome:* `{name}`\n\n"
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
