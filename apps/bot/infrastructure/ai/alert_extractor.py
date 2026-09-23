"""
Extração de intenções em linguagem natural para criação de alertas no Imóvel Radar.

Usa OpenAI com Structured Outputs (JSON Schema estrito) e fallback local/mock determinístico.
"""

from __future__ import annotations

import difflib
import json
import logging
import re
import unicodedata
from typing import Any, Literal

import httpx
from pydantic import BaseModel

logger = logging.getLogger(__name__)

CanonicalCategory = Literal["Apartamentos", "Casas", "Aluguel de quartos"]
ListingKind = Literal["aluguel", "venda"]
Municipality = Literal["Maceió", "Recife", "Natal"]


class ExtractedAlert(BaseModel):
    """Dados extraídos da mensagem de linguagem natural do usuário."""

    municipality: str | None = None
    listing_kind: ListingKind | None = None
    categories: list[CanonicalCategory] | None = None
    min_price: int | None = None
    max_price: int | None = None
    min_rooms: int | None = None
    neighbourhoods: list[str] | None = None


# Schema estrito para OpenAI Structured Outputs
OPENAI_ALERT_EXTRACTION_SCHEMA: dict[str, Any] = {
    "name": "alert_extraction",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "municipality": {
                "anyOf": [
                    {"type": "string", "enum": ["Maceió", "Recife", "Natal"]},
                    {"type": "null"},
                ],
                "description": "Cidade do imóvel ou null se não identificada com certeza.",
            },
            "listing_kind": {
                "anyOf": [
                    {"type": "string", "enum": ["aluguel", "venda"]},
                    {"type": "null"},
                ],
                "description": "Tipo de negócio: 'aluguel' ou 'venda', ou null se ambíguo.",
            },
            "categories": {
                "anyOf": [
                    {
                        "type": "array",
                        "items": {
                            "type": "string",
                            "enum": ["Apartamentos", "Casas", "Aluguel de quartos"],
                        },
                    },
                    {"type": "null"},
                ],
                "description": (
                    "Categorias de imóvel. Apê/kitnet/flat/studio -> 'Apartamentos'. "
                    "Se qualquer, null."
                ),
            },
            "min_price": {
                "anyOf": [{"type": "integer"}, {"type": "null"}],
                "description": "Preço mínimo em reais ou null.",
            },
            "max_price": {
                "anyOf": [{"type": "integer"}, {"type": "null"}],
                "description": "Preço máximo em reais ou null.",
            },
            "min_rooms": {
                "anyOf": [{"type": "integer"}, {"type": "null"}],
                "description": "Mínimo de quartos desejado ou null se qualquer.",
            },
            "neighbourhoods": {
                "anyOf": [
                    {"type": "array", "items": {"type": "string"}},
                    {"type": "null"},
                ],
                "description": "Lista de nomes brutos de bairros citados pelo usuário.",
            },
        },
        "required": [
            "municipality",
            "listing_kind",
            "categories",
            "min_price",
            "max_price",
            "min_rooms",
            "neighbourhoods",
        ],
        "additionalProperties": False,
    },
}

SYSTEM_PROMPT = """Você é o extrator de intenções do Imóvel Radar (bot de alertas imobiliários).
Sua missão é extrair do texto do usuário os critérios de busca em JSON estruturado.

Regras de negócio:
1. Cidades suportadas: 'Maceió', 'Recife' e 'Natal'. Se o usuário não citar a cidade mas citar
   um bairro famoso (ex: Ponta Verde/Jatiúca/Pajuçara -> Maceió; Boa Viagem/Pina/Graças -> Recife;
   Ponta Negra/Tirol/Petrópolis -> Natal), infira a cidade. 'mcz' = Maceió. Se desconhecida, null.
2. Tipo de transação (listing_kind): 'aluguel' ou 'venda'. Se não estiver explícito:
   - Se o preço máximo for <= 20.000, infira 'aluguel'.
   - Se o preço máximo ou mínimo for >= 50.000, infira 'venda'.
   - Entre 20.000 e 50.000 ou sem preço, deixe null.
3. Categorias: apenas 'Apartamentos', 'Casas', 'Aluguel de quartos'.
   - kitnet, loft, flat, studio, ap, apê, apartamento -> 'Apartamentos'.
   - Se o usuário não especificar tipo, deixe categories = null.
4. Preço: converta expressões como '400k' -> 400000, '400 mil' -> 400000, '2.500' -> 2500,
   '3 mil' -> 3000. 'até 400 mil' significa max_price = 400000 e min_price = null.
5. Quartos: '2 quartos', '2 dorms', '2 qts', '2+' -> min_rooms = 2.
6. Bairros: extraia os nomes dos bairros citados.
   Reconheça 'PV' -> 'Ponta Verde', 'BV' -> 'Boa Viagem'.
"""


def _normalize_name(name: str) -> str:
    nfkd = unicodedata.normalize("NFKD", name)
    no_accents = "".join(c for c in nfkd if not unicodedata.combining(c))
    return no_accents.strip().lower()


_SYNONYMS: dict[str, str] = {
    "pv": "ponta verde",
    "bv": "boa viagem",
    "ponta negra": "ponta negra",
}


def match_neighbourhoods(
    raw_neighbourhoods: list[str] | None,
    available_neighbourhoods: list[str],
) -> list[str]:
    """Mapeia nomes de bairros citados para a lista oficial disponível no banco.

    Ignora maiúsculas, acentos e faz fuzzy match para pequenas variações de grafia.
    """
    if not raw_neighbourhoods or not available_neighbourhoods:
        return []

    norm_to_canonical = {_normalize_name(nb): nb for nb in available_neighbourhoods}
    available_norms = list(norm_to_canonical.keys())

    matched: list[str] = []
    for raw in raw_neighbourhoods:
        clean_raw = raw.strip()
        if not clean_raw:
            continue
        norm_raw = _normalize_name(clean_raw)
        norm_raw = _SYNONYMS.get(norm_raw, norm_raw)

        # 1. Match exato normalizado
        if norm_raw in norm_to_canonical:
            canon = norm_to_canonical[norm_raw]
            if canon not in matched:
                matched.append(canon)
            continue

        # 2. Fuzzy match com cutoff alto (0.8)
        close = difflib.get_close_matches(norm_raw, available_norms, n=1, cutoff=0.8)
        if close:
            canon = norm_to_canonical[close[0]]
            if canon not in matched:
                matched.append(canon)

    return matched


# Heurísticas para mock local (dev e testes determinísticos)
_KNOWN_NEIGHBOURHOOD_CITIES: dict[str, str] = {
    # Maceió
    "ponta verde": "Maceió",
    "pv": "Maceió",
    "jatiuca": "Maceió",
    "jatiúca": "Maceió",
    "pajucara": "Maceió",
    "pajuçara": "Maceió",
    "mangabeiras": "Maceió",
    "cruz das almas": "Maceió",
    "farol": "Maceió",
    "serraria": "Maceió",
    "antares": "Maceió",
    "tabuleiro": "Maceió",
    "gruta": "Maceió",
    "jacarecica": "Maceió",
    "centro maceio": "Maceió",
    # Recife
    "boa viagem": "Recife",
    "bv": "Recife",
    "pina": "Recife",
    "gracas": "Recife",
    "graças": "Recife",
    "espinheiro": "Recife",
    "madalena": "Recife",
    "casa forte": "Recife",
    "setubal": "Recife",
    "setúbal": "Recife",
    "jaqueira": "Recife",
    "derby": "Recife",
    # Natal
    "ponta negra": "Natal",
    "tirol": "Natal",
    "petropolis": "Natal",
    "petrópolis": "Natal",
    "candelaria": "Natal",
    "candelária": "Natal",
    "capim macio": "Natal",
    "lagoa nova": "Natal",
}


def mock_extract_alert(text: str) -> ExtractedAlert:
    """Extrai entidades estruturadas por regras determinísticas para dev e testes."""
    norm = _normalize_name(text)

    # 1. Cidade
    city: str | None = None
    if re.search(r"\b(maceio|mcz|alagoas)\b", norm):
        city = "Maceió"
    elif re.search(r"\b(recife|pe|pernambuco)\b", norm):
        city = "Recife"
    elif re.search(r"\b(natal|rn|rio grande do norte)\b", norm):
        city = "Natal"

    # Se ainda sem cidade, procura bairros conhecidos no texto
    detected_nbs: list[str] = []
    for nb_name, nb_city in _KNOWN_NEIGHBOURHOOD_CITIES.items():
        pattern = r"\b" + re.escape(nb_name) + r"\b"
        if re.search(pattern, norm):
            canon_name = _SYNONYMS.get(nb_name, nb_name).title()
            if canon_name not in detected_nbs:
                detected_nbs.append(canon_name)
            if city is None:
                city = nb_city

    # 2. Tipo de transação (aluguel / venda)
    kind: ListingKind | None = None
    if re.search(r"\b(aluguel|alugar|locacao|locação|alugo|aluga)\b", norm):
        kind = "aluguel"
    elif re.search(r"\b(comprar|compra|venda|compro|compro)\b", norm):
        kind = "venda"

    # 3. Categorias
    categories: list[CanonicalCategory] | None = None
    if re.search(r"\b(ap|ape|apê|apto|apartamento|apartamentos|flat|studio|kitnet|loft)\b", norm):
        categories = ["Apartamentos"]
    elif re.search(r"\b(casa|casas|sobrado)\b", norm):
        categories = ["Casas"]
    elif (
        re.search(r"\b(quarto|quartos para alugar)\b", norm)
        and not re.search(r"\d+\s*quartos", norm)
    ):
        categories = ["Aluguel de quartos"]

    # 4. Preços
    min_price: int | None = None
    max_price: int | None = None

    # Ex: "entre 1500 e 3000", "de 200 mil a 400 mil"
    range_match = re.search(
        r"(?:entre|de)\s*(\d+[\.,]?\d*)\s*(mil|k)?\s*(?:e|a|ate|até)\s*(\d+[\.,]?\d*)\s*(mil|k)?",
        norm,
    )
    if range_match:
        p1_raw, p1_unit, p2_raw, p2_unit = range_match.groups()
        p1 = float(p1_raw.replace(".", "").replace(",", "."))
        p2 = float(p2_raw.replace(".", "").replace(",", "."))
        if p1_unit or (p2_unit and p1 < 1000):
            p1 *= 1000
        if p2_unit:
            p2 *= 1000
        min_price = int(p1)
        max_price = int(p2)
    else:
        # Ex: "até 400 mil", "no max 2.500", "até 400k"
        max_match = re.search(
            r"(?:ate|até|no maximo|no máximo|no max|maximo de|máximo de|"
            r"no valor de|por ate|por até)?"
            r"\s*(?:r\$)?\s*(\d+[\.,]?\d*)\s*(mil|k)?\b",
            norm,
        )
        if max_match and max_match.group(1):
            val_raw, unit = max_match.groups()
            try:
                val = float(val_raw.replace(".", "").replace(",", "."))
                if unit:
                    val *= 1000
                elif val < 200 and ("mil" in norm or "k" in norm):
                    val *= 1000
                if val >= 300:  # Evita capturar número de quartos como preço
                    max_price = int(val)
            except ValueError:
                pass

    # Inferência de kind se ambíguo e preço presente
    if kind is None and max_price is not None:
        if max_price <= 20000:
            kind = "aluguel"
        elif max_price >= 50000:
            kind = "venda"

    # 5. Quartos
    min_rooms: int | None = None
    rooms_match = re.search(r"(\d+)\s*(?:\+|mais)?\s*(?:quartos?|dorms?|dormitorios?|qts?)\b", norm)
    if rooms_match:
        try:
            min_rooms = int(rooms_match.group(1))
        except ValueError:
            pass

    return ExtractedAlert(
        municipality=city,
        listing_kind=kind,
        categories=categories,
        min_price=min_price,
        max_price=max_price,
        min_rooms=min_rooms,
        neighbourhoods=detected_nbs or None,
    )


async def extract_alert_with_openai(
    text: str,
    *,
    api_key: str,
    model: str = "gpt-4o-mini",
    timeout_s: float = 8.0,
) -> ExtractedAlert | None:
    """Envia o texto para a OpenAI Chat Completions com JSON Schema estrito."""
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": text},
        ],
        "response_format": {
            "type": "json_schema",
            "json_schema": OPENAI_ALERT_EXTRACTION_SCHEMA,
        },
        "temperature": 0.0,
    }

    try:
        async with httpx.AsyncClient(timeout=timeout_s) as client:
            resp = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            if resp.status_code != 200:
                logger.warning(
                    "OpenAI retornou status %s ao extrair alerta: %s",
                    resp.status_code,
                    resp.text[:300],
                )
                return None

            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            parsed = json.loads(content)
            return ExtractedAlert(**parsed)
    except httpx.TimeoutException:
        logger.warning("Timeout (%.1fs) chamando OpenAI para extração de alerta", timeout_s)
        return None
    except Exception:
        logger.exception("Falha inesperada ao chamar OpenAI para extração de alerta")
        return None


async def extract_alert_intent(
    text: str,
    *,
    provider: str = "mock",
    api_key: str = "",
    model: str = "gpt-4o-mini",
    timeout_s: float = 8.0,
) -> ExtractedAlert | None:
    """Ponto de entrada único para extrair critérios de alerta.

    Fallback gracioso: se o provedor OpenAI falhar (erro, timeout ou sem chave),
    retorna extração pelo mock local determinístico para manter o usuário avançando.
    """
    cleaned = (text or "").strip()
    if not cleaned:
        return None

    if provider == "openai" and api_key:
        result = await extract_alert_with_openai(
            cleaned,
            api_key=api_key,
            model=model,
            timeout_s=timeout_s,
        )
        if result is not None:
            return result
        logger.info("Usando fallback de extração local após falha na OpenAI")

    return mock_extract_alert(cleaned)
