"""
Textos centralizados do bot: boas-vindas, wizard, seeds e mensagens de erro.

Funções puras que retornam ``str`` (muitas em Markdown). Os handlers montam a
resposta com ``parse_mode`` adequado; aqui só fica o conteúdo para facilitar
ajuste de copy e tradução sem espalhar strings nos handlers.
"""

from __future__ import annotations

from telegram.helpers import escape_markdown


def start_welcome() -> str:
    return "👋 *Olá!* Sou o bot de alertas OLX — *Maceió/AL*.\n\n"


def menu_principal_inline() -> str:
    return "🏠 *Menu principal*\nEscolha uma opção:"


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
