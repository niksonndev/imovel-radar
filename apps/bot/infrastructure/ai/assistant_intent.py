"""
Roteamento de intenções do assistente de linguagem natural do Imóvel Radar.

Escolhe QUAL ferramenta acionar (criar/remover/listar alertas, consultar mercado)
e os argumentos mínimos dela — em uma única chamada estruturada, com fallback
determinístico (mock) para dev/testes e para quando a OpenAI falhar.

A extração DETALHADA dos critérios de um alerta novo continua no
``alert_extractor`` (``ExtractedAlert``); aqui só decidimos o verbo e, quando
relevante, cidade/tipo/bairro/referência de alerta.
"""

from __future__ import annotations

import json
import logging
import re
import unicodedata
from typing import Any, Literal

import httpx
from pydantic import BaseModel

logger = logging.getLogger(__name__)

AssistantTool = Literal[
    "criar_alerta",
    "remover_alertas",
    "listar_alertas",
    "consultar_mercado",
    "ajuda",
    "nada",
]

MUNICIPALITIES = ["Maceió", "Recife", "Natal"]


class AssistantIntent(BaseModel):
    """Decisão do agente: qual ferramenta e com quais argumentos mínimos."""

    tool: AssistantTool
    # remover_alertas: referência livre do alerta (nome/bairro/cidade/etc.)
    alert_ref: str | None = None
    # consultar_mercado / criar_alerta
    municipality: str | None = None
    listing_kind: Literal["aluguel", "venda"] | None = None
    neighbourhoods: list[str] | None = None


ASSISTANT_SCHEMA: dict[str, Any] = {
    "name": "assistant_intent",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "tool": {
                "type": "string",
                "enum": [
                    "criar_alerta",
                    "remover_alertas",
                    "listar_alertas",
                    "consultar_mercado",
                    "ajuda",
                    "nada",
                ],
                "description": (
                    "Ação que o usuário pede. 'criar_alerta' se ele quer montar/registrar/achar um "
                    "imóvel novo; 'remover_alertas' se quer apagar/excluir/parar de receber um "
                    "alerta; 'listar_alertas' se quer ver/consultar os alertas dele; "
                    "'consultar_mercado' se pergunta preço/média; 'ajuda' se pede "
                    "help/o que você faz; 'nada' para conversa solta fora desses casos."
                ),
            },
            "alert_ref": {
                "anyOf": [{"type": "string"}, {"type": "null"}],
                "description": (
                    "Só para 'remover_alertas': trecho que identifica o alerta "
                    "(nome, bairro ou cidade). Caso contrário null."
                ),
            },
            "municipality": {
                "anyOf": [
                    {"type": "string", "enum": MUNICIPALITIES},
                    {"type": "null"},
                ],
                "description": "Cidade citada (Maceió, Recife, Natal) ou null.",
            },
            "listing_kind": {
                "anyOf": [
                    {"type": "string", "enum": ["aluguel", "venda"]},
                    {"type": "null"},
                ],
                "description": "Aluguel ou venda citado, ou null.",
            },
            "neighbourhoods": {
                "anyOf": [
                    {"type": "array", "items": {"type": "string"}},
                    {"type": "null"},
                ],
                "description": "Bairros citados ou null.",
            },
        },
        "required": [
            "tool",
            "alert_ref",
            "municipality",
            "listing_kind",
            "neighbourhoods",
        ],
        "additionalProperties": False,
    },
}


ASSISTANT_SYSTEM_PROMPT = """Você é o roteador de intenções do Imóvel Radar
(bot de alertas imobiliários no Telegram). O usuário escreve mensagens livres
para seu assistente. Escolha UMA ferramenta e preencha os argumentos mínimos.

Ferramentas:
1. 'criar_alerta' — montar/registrar/achar um imóvel novo
   (ex: "quero um apartamento em Ponta Verde até 2 mil"). Só município/tipo/
   bairros se óbvios; não preencha os critérios detalhados aqui.
2. 'remover_alertas' — apagar/excluir/remover/cancelar um alerta existente.
   Preencha 'alert_ref' com o que identifica o alerta (nome, bairro, cidade).
3. 'listar_alertas' — ver/consultar os alertas do usuário
   ("quais são meus alertas?", "meus alertas").
4. 'consultar_mercado' — pergunta de preço/média/mercado
   (ex: "média de aluguel em Jatiúca?"). Preencha município/tipo/bairros.
5. 'ajuda' — ajuda/o que o bot faz.
6. 'nada' — conversa solta fora desses escopos.

Cidades: Maceió, Recife, Natal. Tipos: aluguel, venda."""


def _normalize(name: str) -> str:
    nfkd = unicodedata.normalize("NFKD", name)
    no_accents = "".join(c for c in nfkd if not unicodedata.combining(c))
    return no_accents.strip().lower()


_REMOVE_VERBS = (
    "remover",
    "remova",
    "remove",
    "removendo",
    "apagar",
    "apaga",
    "excluir",
    "exclua",
    "cancelar",
    "tirar",
    "tira",
    "para de",
)
_LIST_MARKERS = (
    "listar alerta",
    "meus alerta",
    "meus alertas",
    "quais alerta",
    "quais são meus",
    "mostra meus",
    "ver meus",
    "consultar alerta",
    "mostrar alerta",
)
_CREATE_MARKERS = (
    "novo alerta",
    "criar alerta",
    "montar alerta",
    "criar um alerta",
    "adicionar alerta",
    "quero um",
    "quero alugar",
    "quero comprar",
    "procurar imóvel",
    "quero achar",
    "registrar alerta",
)
_HELP_MARKERS = (
    "ajuda",
    "help",
    "o que você faz",
    "o que vc faz",
    "como funciona",
    "comandos",
    "ajude",
)


def _detect_municipality(norm: str) -> str | None:
    if re.search(r"\b(maceio|mcz|alagoas)\b", norm):
        return "Maceió"
    if re.search(r"\b(recife|pe)\b", norm):
        return "Recife"
    if re.search(r"\b(natal|rn)\b", norm):
        return "Natal"
    return None


def _detect_kind(norm: str) -> Literal["aluguel", "venda"] | None:
    if re.search(r"\b(aluguel|alugar|locacao|locação|alugo|aluga)\b", norm):
        return "aluguel"
    if re.search(r"\b(comprar|compra|venda|compro)\b", norm):
        return "venda"
    return None


def mock_extract_assistant_intent(text: str) -> AssistantIntent:
    """Roteamento determinístico por palavras-chave (dev/testes/fallback)."""
    norm = _normalize(text)
    municipality = _detect_municipality(norm)
    kind = _detect_kind(norm)

    if any(v in norm for v in _REMOVE_VERBS):
        # 'alert_ref' fica com o texto depois do verbo, se houver; senão None.
        ref = None
        for verb in _REMOVE_VERBS:
            idx = norm.find(verb)
            if idx != -1:
                tail = text[idx + len(verb) :].strip(" :.,")
                if tail:
                    ref = tail
                break
        return AssistantIntent(tool="remover_alertas", alert_ref=ref)

    if any(_normalize(m) in norm for m in _LIST_MARKERS):
        return AssistantIntent(tool="listar_alertas")

    # Pergunta de mercado: citou preço/média/mercado ou só cidade+bairro
    if re.search(r"\b(media|média|quanto|preço|preco|mercado|valor|custa)\b", norm):
        return AssistantIntent(
            tool="consultar_mercado",
            municipality=municipality,
            listing_kind=kind,
        )

    if any(_normalize(c) in norm for c in _CREATE_MARKERS) or (
        municipality is not None and kind is not None
    ):
        return AssistantIntent(tool="criar_alerta")

    if any(_normalize(h) in norm for h in _HELP_MARKERS):
        return AssistantIntent(tool="ajuda")

    return AssistantIntent(tool="nada")


async def extract_assistant_intent_with_openai(
    text: str,
    *,
    api_key: str,
    model: str = "gpt-4o-mini",
    timeout_s: float = 8.0,
) -> AssistantIntent | None:
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": ASSISTANT_SYSTEM_PROMPT},
            {"role": "user", "content": text},
        ],
        "response_format": {
            "type": "json_schema",
            "json_schema": ASSISTANT_SCHEMA,
        },
        "temperature": 0.0,
    }
    try:
        async with httpx.AsyncClient(timeout=timeout_s) as client:
            resp = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json=payload,
            )
            if resp.status_code != 200:
                logger.warning(
                    "OpenAI retornou %s ao rotear intenção: %s", resp.status_code, resp.text[:300]
                )
                return None
            content = resp.json()["choices"][0]["message"]["content"]
            return AssistantIntent(**json.loads(content))
    except httpx.TimeoutException:
        logger.warning("Timeout (%.1fs) roteando intenção", timeout_s)
        return None
    except Exception:
        logger.exception("Falha inesperada ao rotear intenção")
        return None


async def extract_assistant_intent(
    text: str,
    *,
    provider: str = "mock",
    api_key: str = "",
    model: str = "gpt-4o-mini",
    timeout_s: float = 8.0,
) -> AssistantIntent:
    """Escolhe a intenção do usuário, com fallback determinístico."""
    cleaned = (text or "").strip()
    if not cleaned:
        return AssistantIntent(tool="nada")
    if provider == "openai" and api_key:
        result = await extract_assistant_intent_with_openai(
            cleaned, api_key=api_key, model=model, timeout_s=timeout_s
        )
        if result is not None:
            return result
        logger.info("Fallback local após falha ao rotear intenção")
    return mock_extract_assistant_intent(cleaned)
