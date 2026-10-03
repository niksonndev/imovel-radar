"""Fatias de preço: deactivate só na última; cursor passa ps/pe."""

from __future__ import annotations

import asyncio

import config
from collector.olx_scraper import SearchChunkResult
from scheduler import jobs
from scheduler.jobs import should_deactivate_after_slice, slices_for_kind


class _Result:
    def one(self) -> int:
        return 0


class _Session:
    def __init__(self, _engine) -> None:
        pass

    def __enter__(self) -> _Session:
        return self

    def __exit__(self, *_args) -> bool:
        return False

    def exec(self, *_args, **_kwargs) -> _Result:
        # Cobre marcar_fatia (insert) e fatias_pendentes (select → 0 fatias,
        # que bloqueia a inativação; quem testa inativação patcheia a função).
        return _Result()

    def commit(self) -> None:
        return None


def test_should_deactivate_only_on_last_slice() -> None:
    assert should_deactivate_after_slice("aluguel", 0, completed=True) is True
    assert should_deactivate_after_slice("venda", 0, completed=True) is False
    assert should_deactivate_after_slice("venda", 1, completed=False) is False
    last = len(config.SALE_PRICE_SLICES) - 1
    assert should_deactivate_after_slice("venda", last, completed=True) is True


def test_middle_slice_does_not_deactivate(monkeypatch) -> None:
    calls: list[dict] = []

    async def fake_search(*_args, **_kwargs) -> SearchChunkResult:
        return SearchChunkResult(listings=[], completed=True, listing_kind="venda")

    monkeypatch.setattr(jobs, "search_listings", fake_search)
    monkeypatch.setattr(jobs, "Session", _Session)
    monkeypatch.setattr(
        jobs,
        "deactivate_missing_listings",
        lambda *_a, **kwargs: calls.append(kwargs) or 1,
    )

    result = asyncio.run(jobs.job_collect_chunk(listing_kind="venda", slice_index=1))

    assert result["success"] == 1
    assert result["completed"] is True
    assert result["deactivated"] == 0
    assert calls == []


def test_last_slice_deactivates(monkeypatch) -> None:
    calls: list[dict] = []
    last = len(config.SALE_PRICE_SLICES) - 1

    async def fake_search(*_args, **_kwargs) -> SearchChunkResult:
        return SearchChunkResult(listings=[], completed=True, listing_kind="venda")

    monkeypatch.setattr(jobs, "search_listings", fake_search)
    monkeypatch.setattr(jobs, "Session", _Session)
    monkeypatch.setattr(
        jobs,
        "deactivate_missing_listings",
        lambda *_a, **kwargs: calls.append(kwargs) or 4,
    )
    monkeypatch.setattr(jobs, "marcar_fatia", lambda *_a, **_k: None)
    monkeypatch.setattr(jobs, "fatias_pendentes", lambda *_a, **_k: 0)

    result = asyncio.run(jobs.job_collect_chunk(listing_kind="venda", slice_index=last))

    assert result["deactivated"] == 4
    assert len(calls) == 1
    assert calls[0]["listing_kind"] == "venda"
    assert calls[0]["source_market"] == "maceio"


def test_job_passes_price_bounds_for_slice(monkeypatch) -> None:
    captured: dict = {}

    async def fake_search(*_args, **kwargs) -> SearchChunkResult:
        captured.update(kwargs)
        return SearchChunkResult(completed=False, next_page=2, listing_kind="venda")

    monkeypatch.setattr(jobs, "search_listings", fake_search)
    monkeypatch.setattr(jobs, "Session", _Session)

    result = asyncio.run(jobs.job_collect_chunk(listing_kind="venda", slice_index=2))

    assert captured["price_min"] == 500_000
    assert captured["price_max"] == 700_000
    assert result["completed"] is False
    assert result["next_page"] == 2
    assert result["deactivated"] == 0


def test_recife_rent_deactivates_only_on_last_slice() -> None:
    assert should_deactivate_after_slice("aluguel", 0, completed=True, market="recife") is False
    last = len(slices_for_kind("aluguel", "recife")) - 1
    assert should_deactivate_after_slice("aluguel", last, completed=True, market="recife") is True


def test_recife_last_slice_deactivates_recife(monkeypatch) -> None:
    calls: list[dict] = []
    last = len(slices_for_kind("venda", "recife")) - 1

    async def fake_search(*_args, **_kwargs) -> SearchChunkResult:
        return SearchChunkResult(listings=[], completed=True, listing_kind="venda")

    monkeypatch.setattr(jobs, "search_listings", fake_search)
    monkeypatch.setattr(jobs, "Session", _Session)
    monkeypatch.setattr(
        jobs,
        "deactivate_missing_listings",
        lambda *_a, **kwargs: calls.append(kwargs) or 2,
    )
    monkeypatch.setattr(jobs, "marcar_fatia", lambda *_a, **_k: None)
    monkeypatch.setattr(jobs, "fatias_pendentes", lambda *_a, **_k: 0)

    result = asyncio.run(
        jobs.job_collect_chunk(listing_kind="venda", market="recife", slice_index=last)
    )

    assert result["deactivated"] == 2
    assert calls[0]["source_market"] == "recife"
    assert calls[0]["listing_kind"] == "venda"


def test_natal_rent_deactivates_on_last_slice() -> None:
    # Natal rent tem apenas 1 fatia aberta (índice 0 é a última)
    assert should_deactivate_after_slice("aluguel", 0, completed=True, market="natal") is True


def test_natal_last_slice_deactivates_natal(monkeypatch) -> None:
    calls: list[dict] = []
    last = len(slices_for_kind("venda", "natal")) - 1

    async def fake_search(*_args, **_kwargs) -> SearchChunkResult:
        return SearchChunkResult(listings=[], completed=True, listing_kind="venda")

    monkeypatch.setattr(jobs, "search_listings", fake_search)
    monkeypatch.setattr(jobs, "Session", _Session)
    monkeypatch.setattr(
        jobs,
        "deactivate_missing_listings",
        lambda *_a, **kwargs: calls.append(kwargs) or 3,
    )
    monkeypatch.setattr(jobs, "marcar_fatia", lambda *_a, **_k: None)
    monkeypatch.setattr(jobs, "fatias_pendentes", lambda *_a, **_k: 0)

    result = asyncio.run(
        jobs.job_collect_chunk(listing_kind="venda", market="natal", slice_index=last)
    )

    assert result["deactivated"] == 3
    assert calls[0]["source_market"] == "natal"
    assert calls[0]["listing_kind"] == "venda"


def test_clamped_slice_does_not_deactivate(monkeypatch) -> None:
    calls: list[dict] = []
    last = len(slices_for_kind("venda", "recife")) - 1

    async def fake_search(*_args, **_kwargs) -> SearchChunkResult:
        return SearchChunkResult(
            listings=[],
            completed=False,
            clamped=True,
            listing_kind="venda",
        )

    monkeypatch.setattr(jobs, "search_listings", fake_search)
    monkeypatch.setattr(jobs, "Session", _Session)
    monkeypatch.setattr(
        jobs,
        "deactivate_missing_listings",
        lambda *_a, **kwargs: calls.append(kwargs) or 9,
    )

    result = asyncio.run(
        jobs.job_collect_chunk(listing_kind="venda", market="recife", slice_index=last)
    )

    assert result["completed"] is False
    assert result["clamped"] is True
    assert result["deactivated"] == 0
    assert calls == []


def test_inativacao_adiada_quando_alguma_fatia_nao_concluiu(monkeypatch) -> None:
    """Fatia clampada/morta no run bloqueia a inativação inteira.

    Senão a última fatia inativaria anúncio que a fatia clampada nunca chegou a
    olhar — tirando do ar anúncio vivo e re-notificando na volta.
    """
    calls: list[dict] = []
    last = len(config.SALE_PRICE_SLICES) - 1

    async def fake_search(*_args, **_kwargs) -> SearchChunkResult:
        return SearchChunkResult(listings=[], completed=True, listing_kind="venda")

    monkeypatch.setattr(jobs, "search_listings", fake_search)
    monkeypatch.setattr(jobs, "Session", _Session)
    monkeypatch.setattr(jobs, "marcar_fatia", lambda *_a, **_k: None)
    monkeypatch.setattr(jobs, "fatias_pendentes", lambda *_a, **_k: 2)
    monkeypatch.setattr(
        jobs,
        "deactivate_missing_listings",
        lambda *_a, **kwargs: calls.append(kwargs) or 7,
    )

    result = asyncio.run(jobs.job_collect_chunk(listing_kind="venda", slice_index=last))

    assert result["deactivated"] == 0
    assert calls == []


def test_marca_status_da_fatia_ao_terminar(monkeypatch) -> None:
    """A fatia reporta como terminou; a última consulta o placar do run."""
    marcadas: list[dict] = []

    async def fake_search(*_args, **_kwargs) -> SearchChunkResult:
        return SearchChunkResult(
            listings=[], completed=False, clamped=True, listing_kind="venda"
        )

    monkeypatch.setattr(jobs, "search_listings", fake_search)
    monkeypatch.setattr(jobs, "Session", _Session)
    monkeypatch.setattr(jobs, "marcar_fatia", lambda *_a, **kw: marcadas.append(kw))
    monkeypatch.setattr(jobs, "fatias_pendentes", lambda *_a, **_k: 0)

    asyncio.run(
        jobs.job_collect_chunk(
            listing_kind="venda", market="recife", slice_index=2, skip_deactivate=True
        )
    )

    assert len(marcadas) == 1
    assert marcadas[0]["status"] == "clamped"
    assert marcadas[0]["market"] == "recife"
    assert marcadas[0]["slice_index"] == 2


def _listing_dict(listing_id: int) -> dict:
    return {
        "listing_id": listing_id,
        "listing_kind": "venda",
        "url": f"https://exemplo.com/{listing_id}",
        "title": f"Imóvel {listing_id}",
        "price_value": 1000,
        "old_price": None,
        "municipality": "Recife",
        "neighbourhood": "Boa Viagem",
        "category": "Apartamento",
        "images": [],
        "properties": {},
    }


def test_delta_nao_inativa_nunca(monkeypatch) -> None:
    """Delta = recência. Um walk de 3 páginas não sabe o que saiu do ar.

    Se este teste quebrar, o corpus inteiro vira inativo na primeira hora.
    """
    chamadas: list[dict] = []

    async def fake_search(*_args, **_kwargs) -> SearchChunkResult:
        return SearchChunkResult(
            listings=[_listing_dict(1), _listing_dict(2)],  # type: ignore[list-item]
            completed=True,
            listing_kind="venda",
        )

    monkeypatch.setattr(jobs, "search_listings", fake_search)
    monkeypatch.setattr(jobs, "Session", _Session)
    monkeypatch.setattr(jobs, "upsert_listing", lambda *_a, **_k: None)
    monkeypatch.setattr(
        jobs,
        "deactivate_missing_listings",
        lambda *_a, **kwargs: chamadas.append(kwargs) or 0,
    )

    result = asyncio.run(jobs.job_collect_delta(markets=["recife"], pages=3))

    assert result["success"] == 1
    assert result["count"] == 4  # 2 tipos × 2 anúncios
    assert chamadas == []


def test_delta_grava_escopo_do_mercado(monkeypatch) -> None:
    """O delta adota a linha: a varredura completa usa `source_market` p/ inativar."""
    escopos: list[str] = []

    async def fake_search(*_args, **_kwargs) -> SearchChunkResult:
        return SearchChunkResult(
            listings=[_listing_dict(7)],  # type: ignore[list-item]
            completed=True,
            listing_kind="aluguel",
        )

    monkeypatch.setattr(jobs, "search_listings", fake_search)
    monkeypatch.setattr(jobs, "Session", _Session)
    monkeypatch.setattr(
        jobs,
        "upsert_listing",
        lambda _s, _l, *, source_market: escopos.append(source_market),
    )

    asyncio.run(jobs.job_collect_delta(markets=["natal"], pages=1))

    assert set(escopos) == {"natal"}
