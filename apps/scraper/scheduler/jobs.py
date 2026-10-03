"""Coleção diária do OLX (aluguel + venda), em chunks por invocação Lambda.

``job_collect_chunk`` coleta uma janela de páginas, persiste, e retorna
metadados para o handler decidir self-invoke / deactivate. Notificações
continuam responsabilidade do bot (ADR 0005).
"""

from __future__ import annotations

import asyncio
import logging
import os
import random
import time
from datetime import UTC, datetime
from typing import Any, Callable

from shared_models.tables import Listing, ListingKind
from sqlalchemy import func as sql_func
from sqlalchemy.exc import DBAPIError
from sqlmodel import Session, col, select

import config
from collector import base_url_for_kind, search_listings
from database import engine
from database.queries import (
    deactivate_missing_listings,
    fatias_pendentes,
    marcar_fatia,
    semear_fatias,
    upsert_listing,
)

logger = logging.getLogger(__name__)

RemainingTimeFn = Callable[[], int | None]
PriceSlice = tuple[int | None, int | None]

# Tentativas de gravação de um chunk. O fan-out roda fatias em paralelo
# escrevendo as mesmas linhas: deadlock no Postgres era o normal, não a exceção,
# e um chunk quebrado encerrava a cadeia do dia (a última fatia não completava,
# ninguém inativava e a próxima cidade nunca era visitada).
MAX_PERSIST_ATTEMPTS = 3
# Páginas por passada no delta (cabeça ordenada por recência).
DELTA_PAGES = int(os.getenv("SCRAPER_DELTA_PAGES", "3"))


def _is_retryable_db_error(error: Exception) -> bool:
    """Deadlock/serialização: vale repetir. O resto não."""
    original = getattr(error, "orig", error)
    if type(original).__name__ in {"DeadlockDetected", "SerializationFailure"}:
        return True
    texto = str(error).lower()
    return "deadlock detected" in texto or "could not serialize" in texto


def _semear_com_retry(**kwargs: Any) -> None:
    """``semear_fatias`` com o mesmo retry de deadlock da gravação."""
    for tentativa in range(MAX_PERSIST_ATTEMPTS):
        try:
            with Session(engine) as session:
                semear_fatias(session, **kwargs)
                session.commit()
            return
        except DBAPIError as error:
            if not _is_retryable_db_error(error) or tentativa == MAX_PERSIST_ATTEMPTS - 1:
                raise
            time.sleep(0.5 * (2**tentativa) + random.uniform(0, 0.3))


def _persist_chunk(
    *,
    listings: list[Any],
    source_market: str,
    listing_kind: ListingKind,
    run_started_at: datetime,
    deactivate: bool,
    slice_index: int | None = None,
    slice_status: str | None = None,
    filhas: list[tuple[int, int | None, int | None]] | None = None,
) -> int:
    """Grava um chunk (e inativa, quando é a última fatia) numa transação.

    Ordena por ``listing_id`` de propósito: transações concorrentes travam as
    mesmas linhas, e em ordem diferente isso é receita de deadlock.
    """
    with Session(engine) as session:
        for listing in sorted(listings, key=lambda item: item["listing_id"]):
            upsert_listing(session, listing, source_market=source_market)
        if slice_status is not None and slice_index is not None:
            marcar_fatia(
                session,
                run_started_at=run_started_at,
                market=source_market,
                listing_kind=listing_kind,
                slice_index=slice_index,
                status=slice_status,
            )
        # As filhas nascem AGENDADAS na mesma transação: se a cadeia delas morrer
        # sem rodar, elas ficam 'pending' e o portão de inativação continua
        # fechado (era o furo de confiar que "a última fatia inativa o resto").
        for indice_filha, lo, hi in filhas or []:
            marcar_fatia(
                session,
                run_started_at=run_started_at,
                market=source_market,
                listing_kind=listing_kind,
                slice_index=indice_filha,
                status="pending",
            )
            logger.info(
                "Fatia repartida: faixa [%s, %s) vira a filha %s [%s, %s)",
                None,
                None,
                indice_filha,
                lo,
                hi,
            )
        deactivated = 0
        if deactivate:
            raizes = len(slices_for_kind(listing_kind, source_market))
            pendentes = fatias_pendentes(
                session,
                run_started_at=run_started_at,
                market=source_market,
                listing_kind=listing_kind,
                raizes=raizes,
            )
            if pendentes:
                # Alguma fatia clampou (a OLX para na página 100) ou morreu:
                # inativar aqui tiraria do ar anúncio que ninguém chegou a olhar.
                logger.warning(
                    "Inativação de %s/%s adiada: %s fatia(s) não concluída(s) neste run",
                    source_market,
                    listing_kind,
                    pendentes,
                )
            else:
                deactivated = deactivate_missing_listings(
                    session,
                    source_market=source_market,
                    listing_kind=listing_kind,
                    run_started_at=run_started_at,
                )
        session.commit()
    return deactivated


def _persist_with_retry(**kwargs: Any) -> int:
    """``_persist_chunk`` com retry em deadlock (jitter para não sincronizar)."""
    for tentativa in range(MAX_PERSIST_ATTEMPTS):
        try:
            return _persist_chunk(**kwargs)
        except DBAPIError as error:
            if not _is_retryable_db_error(error) or tentativa == MAX_PERSIST_ATTEMPTS - 1:
                raise
            espera = 0.5 * (2**tentativa) + random.uniform(0, 0.3)
            logger.warning(
                "Deadlock ao gravar chunk (tentativa %s/%s) — repetindo em %.1fs",
                tentativa + 1,
                MAX_PERSIST_ATTEMPTS,
                espera,
            )
            time.sleep(espera)
    raise AssertionError("inalcançável")


def slices_for_kind(
    listing_kind: ListingKind,
    market: str | None = None,
) -> list[PriceSlice]:
    """Fatias de preço da coleta daquele mercado e tipo."""
    chosen = config.market_by_key(market)
    if listing_kind == "venda":
        return list(chosen.sale_slices)
    return list(chosen.rent_slices)


def should_deactivate_after_slice(
    listing_kind: ListingKind,
    slice_index: int,
    *,
    completed: bool,
    market: str | None = None,
    skip_deactivate: bool = False,
) -> bool:
    """Toda fatia tenta inativar; quem decide é o placar (`fatias_pendentes`).

    Antes esta função dizia "só a última fatia inativa", o que supunha que todas
    as outras tinham passado — e elas clampam (a OLX para na página 100). Agora a
    tentativa é livre e o portão exige que TODAS tenham fechado a própria faixa
    (``ok``) ou sido repartidas em filhas que fecharam (``split``).
    """
    del listing_kind, slice_index, market
    return completed and not skip_deactivate


def banda_filha(slice_index: int, primeiro: bool) -> int:
    """Índice da filha de uma fatia repartida.

    Raízes ficam em ``0..N-1`` (índices das fatias do config, que a cadeia usa
    para avançar de tipo/cidade) e as filhas vivem em ``100+``: ``2*i + 100`` e
    ``2*i + 101``. A numeração não colide com as raízes nem entre gerações.
    """
    return 100 + 2 * slice_index + (0 if primeiro else 1)


def repartir_faixa(
    price_min: int | None, price_max: int | None
) -> list[tuple[int | None, int | None]]:
    """Divide uma faixa ao meio para as filhas.

    Sem teto superior não há meio geométrico: corta-se na mediana observada do
    banco (`mediana_de_preco`), que é o que faz a faixa de cima parar de clamp.
    """
    if price_max is None:
        corte = mediana_de_preco(price_min) if price_min is not None else None
        if corte is None:
            return []
        return [(price_min, corte), (corte, None)]
    if price_min is None:
        return [(None, max(1, price_max // 2)), (max(1, price_max // 2), price_max)]
    meio = price_min + (price_max - price_min) // 2
    if meio <= price_min:
        return []
    return [(price_min, meio), (meio, price_max)]


def mediana_de_preco(piso: int | None) -> int | None:
    """Mediana dos preços acima de ``piso`` em qualquer mercado/cidade.

    A OLX devolve o preço do anúncio, então a mediana do que já está no banco é
    uma estimativa boa do meio da faixa — é medida, não chute.
    """
    try:
        with Session(engine) as session:
            consulta = (
                select(
                    sql_func.percentile_cont(0.5).within_group(col(Listing.price_value).asc())
                )
                .select_from(Listing)
                .where(
                    col(Listing.active).is_(True),
                    col(Listing.price_value).is_not(None),
                )
            )
            if piso is not None:
                consulta = consulta.where(col(Listing.price_value) >= piso)
            valor = session.exec(consulta).one()
    except Exception:
        logger.exception("Não consegui medir a mediana de preço (piso=%s)", piso)
        return None
    return int(valor) if valor else None


def parse_run_started_at(raw: str | None) -> datetime:
    if not raw:
        return datetime.now(UTC)
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return datetime.now(UTC)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed


def normalize_kind(raw: Any) -> ListingKind:
    if raw == "venda":
        return "venda"
    return "aluguel"


async def job_collect_chunk(
    *,
    listing_kind: ListingKind = "aluguel",
    market: str | None = None,
    start_page: int = 1,
    slice_index: int = 0,
    attempt: int = 0,
    skip_deactivate: bool = False,
    run_started_at: datetime | None = None,
    get_remaining_ms: RemainingTimeFn | None = None,
    max_pages: int | None = None,
    price_min: int | None = None,
    price_max: int | None = None,
) -> dict[str, Any]:
    """Coleta uma janela de páginas de uma fatia e persiste.

    ``price_min``/``price_max`` explícitos identificam uma fatia FILHA (nascida
    da repartição de uma fatia que clampou) — nesse caso a faixa vem do payload,
    não do config.

    Returns:
      success, count, market, listing_kind, slice_index, completed, clamped,
      next_page, attempt, run_started_at (iso), deactivated, dividir_em (faixas
      filhas quando a OLX clampou).
    """
    chosen = config.market_by_key(market)
    started = run_started_at or datetime.now(UTC)
    slices = slices_for_kind(listing_kind, chosen.key)
    filha = price_min is not None or price_max is not None
    result: dict[str, Any] = {
        "success": 0,
        "count": 0,
        "market": chosen.key,
        "listing_kind": listing_kind,
        "slice_index": slice_index,
        "completed": False,
        "clamped": False,
        "next_page": None,
        "attempt": attempt,
        "skip_deactivate": skip_deactivate,
        "run_started_at": started.isoformat(),
        "deactivated": 0,
        "start_page": start_page,
        "dividir_em": [],
    }
    if not filha and (slice_index < 0 or slice_index >= len(slices)):
        logger.error(
            "slice_index inválido: %s (kind=%s, fatias=%s)",
            slice_index,
            listing_kind,
            len(slices),
        )
        return result

    if not filha:
        price_min, price_max = slices[slice_index]
    if slice_index == 0 and not filha:
        # Marca o tipo inteiro como pendente antes de qualquer fatia rodar: o
        # portão de inativação precisa saber que existem faixas ainda não vistas.
        _semear_com_retry(
            run_started_at=started,
            market=chosen.key,
            listing_kind=listing_kind,
            quantidade=len(slices),
        )
    try:
        logger.info(
            "Collect chunk: start market=%s kind=%s slice=%s/%s page=%s attempt=%s "
            "ps=%s pe=%s run_started_at=%s",
            chosen.key,
            listing_kind,
            slice_index,
            len(slices) - 1,
            start_page,
            attempt,
            price_min,
            price_max,
            started.isoformat(),
        )
        chunk = await search_listings(
            base_url_for_kind(listing_kind, market_key=chosen.key),
            listing_kind=listing_kind,
            start_page=start_page,
            max_pages=max_pages,
            price_min=price_min,
            price_max=price_max,
            attempt=attempt,
            get_remaining_ms=get_remaining_ms,
        )
        deactivate = should_deactivate_after_slice(
            listing_kind,
            slice_index,
            completed=chunk.completed,
            market=chosen.key,
            skip_deactivate=skip_deactivate or chunk.clamped,
        )
        # A fatia só "termina" quando não há próxima página: aí dá para dizer se
        # ela viu o mercado inteiro (ok), se a OLX clampou (aí a faixa é
        # repartida em duas filhas) ou se morreu no meio.
        fim_da_fatia = chunk.next_page is None
        filhas: list[tuple[int, int | None, int | None]] = []
        if not fim_da_fatia:
            status_da_fatia = None
        elif chunk.clamped:
            faixas = repartir_faixa(price_min, price_max)
            if faixas:
                filhas = [
                    (banda_filha(slice_index, indice == 0), lo, hi)
                    for indice, (lo, hi) in enumerate(faixas)
                ]
                status_da_fatia = "split"
            else:
                # Sem mediana não dá para cortar a faixa: fica bloqueando a
                # inativação (melhor não inativar do que inativar às cegas).
                status_da_fatia = "clamped"
        elif chunk.completed:
            status_da_fatia = "ok"
        else:
            status_da_fatia = "failed"
        deactivated = _persist_with_retry(
            listings=chunk.listings,
            source_market=chosen.key,
            listing_kind=listing_kind,
            run_started_at=started,
            deactivate=deactivate,
            slice_index=slice_index,
            slice_status=status_da_fatia,
            filhas=filhas,
        )
        result["dividir_em"] = [
            {"slice_index": indice, "price_min": lo, "price_max": hi}
            for indice, lo, hi in filhas
        ]
        if filhas:
            logger.warning(
                "Fatia %s (kind=%s market=%s) clampou na faixa [%s, %s): repartida em %s",
                slice_index,
                listing_kind,
                chosen.key,
                price_min,
                price_max,
                [ficha["slice_index"] for ficha in result["dividir_em"]],
            )
        if deactivate:
            logger.info(
                "Deactivated %s missing listings (kind=%s slice=%s market=%s)",
                deactivated,
                listing_kind,
                slice_index,
                chosen.key,
            )
        elif chunk.completed:
            logger.info(
                "Fatia %s concluída (kind=%s) — sem deactivate; próxima fatia segue",
                slice_index,
                listing_kind,
            )

        result["success"] = 1
        result["count"] = len(chunk.listings)
        result["completed"] = chunk.completed
        result["clamped"] = chunk.clamped
        result["next_page"] = chunk.next_page
        result["attempt"] = chunk.next_attempt
        result["skip_deactivate"] = skip_deactivate or chunk.clamped
        result["deactivated"] = deactivated
        logger.info(
            "Collect chunk: end market=%s kind=%s slice=%s count=%s completed=%s "
            "clamped=%s next_page=%s attempt=%s",
            chosen.key,
            listing_kind,
            slice_index,
            result["count"],
            chunk.completed,
            chunk.clamped,
            chunk.next_page,
            chunk.next_attempt,
        )
        return result
    except Exception:
        logger.exception("Collect chunk failed (kind=%s slice=%s)", listing_kind, slice_index)
        return result


async def job_daily() -> dict[str, int]:
    """Compat local/manual: coleta aluguel de Maceió até o fim (uma janela grande)."""
    maceio = config.market_by_key("maceio")
    started = datetime.now(UTC)
    total = 0
    page = 1
    while True:
        chunk = await search_listings(
            base_url_for_kind("aluguel", market_key=maceio.key),
            listing_kind="aluguel",
            start_page=page,
            max_pages=config.SCRAPER_MAX_PAGES,
        )
        with Session(engine) as session:
            for listing in sorted(chunk.listings, key=lambda item: item["listing_id"]):
                upsert_listing(session, listing, source_market=maceio.key)
            if chunk.completed and not chunk.clamped:
                deactivate_missing_listings(
                    session,
                    source_market=maceio.key,
                    listing_kind="aluguel",
                    run_started_at=started,
                )
            session.commit()
        total += len(chunk.listings)
        if chunk.completed or not chunk.next_page:
            break
        page = chunk.next_page
    return {"success": 1, "count": total}


async def job_collect_delta(
    *,
    pages: int = DELTA_PAGES,
    markets: list[str] | None = None,
    get_remaining_ms: RemainingTimeFn | None = None,
) -> dict[str, Any]:
    """Passada curta por recência: pega o que é novo, **sem inativar nada**.

    A listagem da OLX já vem ordenada por mais recentes (``sf=1``), então as
    primeiras páginas da URL sem filtro de preço são o que acabou de entrar.
    Custa ~1 request por página (contra ~1 request por 50 anúncios da varredura
    completa) e é o que dá latência de minutos ao alerta.

    Regra que não pode ser quebrada: **nada aqui chama
    ``deactivate_missing_listings``**. Quem inativa é a varredura completa, que
    viu a listagem inteira; um walk de 3 páginas não sabe o que sumiu, e usá-lo
    para inativar marcaria o corpus inteiro como fora do ar. Essas linhas também
    não passam pelo watermark, então a próxima varredura completa continua
    correta: ela vai re-ver o anúncio (atualizando ``updated_at``) ou inativá-lo.
    """
    keys = markets or [market.key for market in config.MARKETS]
    total = 0
    detalhe: dict[str, int] = {}
    for key in keys:
        if get_remaining_ms is not None and (get_remaining_ms() or 10**9) < 30_000:
            logger.warning("Delta: sem tempo restante, parando em %s", key)
            break
        for kind in ("aluguel", "venda"):
            try:
                chunk = await search_listings(
                    base_url_for_kind(kind, market_key=key),
                    listing_kind=kind,  # type: ignore[arg-type]
                    start_page=1,
                    max_pages=max(1, pages),
                )
            except Exception:
                logger.exception("Delta falhou (market=%s kind=%s)", key, kind)
                continue
            if chunk.listings:
                _persist_with_retry(
                    listings=chunk.listings,
                    source_market=key,
                    listing_kind=kind,  # type: ignore[arg-type]
                    run_started_at=datetime.now(UTC),
                    deactivate=False,
                )
            detalhe[f"{key}/{kind}"] = len(chunk.listings)
            total += len(chunk.listings)
    logger.info("Delta: %s anúncios por recência em %s mercados", total, len(keys))
    return {"success": 1, "count": total, "delta": detalhe}


if __name__ == "__main__":
    asyncio.run(job_daily())
