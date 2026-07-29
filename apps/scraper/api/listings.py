"""Endpoints de listings: consulta por IDs, por timestamp, bairros."""

from __future__ import annotations

import json
from typing import Annotated

from fastapi import APIRouter, Query
from shared_models.api_schemas import (
    ListingsListHydratedResponse,
    NeighbourhoodsResponse,
)
from shared_models.models import HydratedListing, Properties

from database import get_connection
from database.queries import get_listings_by_ids, get_maceio_neighbourhoods

router = APIRouter(prefix="/listings", tags=["listings"])


def _hydrate_listing(listing: dict) -> HydratedListing:
    """Converte um dict bruto do banco para HydratedListing."""
    properties_list: list[dict] = (
        json.loads(listing["properties"]) if listing["properties"] else []
    )
    for item in properties_list:
        if "real_estate_type" in item:
            item["real_estate_type"] = item["real_estate_type"].split(" - ")[0]

    return HydratedListing(
        listId=listing["listId"],
        url=listing["url"],
        title=listing["title"],
        priceValue=listing["priceValue"],
        oldPrice=listing["oldPrice"],
        municipality=listing["municipality"],
        neighbourhood=listing["neighbourhood"],
        category=listing["category"],
        images=json.loads(listing["images"]),
        properties=[Properties(**p) for p in properties_list],
    )


@router.get("", response_model=ListingsListHydratedResponse)
async def list_listings(
    ids: Annotated[str | None, Query(description="Comma-separated listing IDs")] = None,
    since: Annotated[str | None, Query(description="ISO timestamp filter")] = None,
) -> ListingsListHydratedResponse:
    """Retorna listings. Filtra por ``ids`` (CSV) ou ``since`` (ISO timestamp)."""
    conn = get_connection()
    try:
        if ids:
            id_list = [int(x.strip()) for x in ids.split(",") if x.strip()]
            rows = get_listings_by_ids(conn, id_list)
        elif since:
            rows = conn.execute(
                "SELECT * FROM listings "
                "WHERE updated_at >= ? AND active = TRUE "
                "ORDER BY updated_at DESC",
                (since,),
            ).fetchall()
            rows = [dict(r) for r in rows]
        else:
            rows = conn.execute(
                "SELECT * FROM listings WHERE active = TRUE ORDER BY updated_at DESC LIMIT 100"
            ).fetchall()
            rows = [dict(r) for r in rows]
    finally:
        conn.close()

    hydrated = [_hydrate_listing(r) for r in rows]
    return ListingsListHydratedResponse(listings=hydrated, total=len(hydrated))


@router.get("/neighbourhoods", response_model=NeighbourhoodsResponse)
async def neighbourhoods() -> NeighbourhoodsResponse:
    """Retorna lista de bairros disponíveis em Maceió."""
    conn = get_connection()
    try:
        nbs = get_maceio_neighbourhoods(conn)
    finally:
        conn.close()
    return NeighbourhoodsResponse(neighbourhoods=nbs)


@router.get("/{list_id}", response_model=HydratedListing)
async def get_listing(list_id: int) -> HydratedListing:
    """Retorna um listing por ID."""
    conn = get_connection()
    try:
        rows = get_listings_by_ids(conn, [list_id])
    finally:
        conn.close()

    if not rows:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Listing não encontrado")

    return _hydrate_listing(rows[0])