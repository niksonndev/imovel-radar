"""Endpoints de listings: consulta por IDs, por timestamp, bairros."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from shared_models.api_schemas import (
    MarkNotifiedRequest,
    UnnotifiedListing,
    UnnotifiedListingsResponse,
)
from shared_models.models import Listing, Properties
from sqlmodel import Session

from database import get_session
from database.models import Listing as ListingModel
from database.queries import (
    get_neighbourhoods,
    get_unnotified_listings_for_user,
    mark_listings_notified_bulk,
)

router = APIRouter(prefix="/listings", tags=["listings"])


def _hydrate_listing(listing: ListingModel) -> Listing:
    """Converte um Listing (SQLModel) para o contrato da API."""
    return Listing(
        listing_id=listing.listing_id,
        url=listing.url or "",
        title=listing.title or "",
        price_value=listing.price_value,
        old_price=listing.old_price,
        municipality=listing.municipality or "",
        neighbourhood=listing.neighbourhood,
        category=listing.category or "",
        images=listing.images,
        properties=Properties(**listing.properties) if listing.properties else Properties(),
        active=listing.active,
    )


@router.get("/{chat_id}/unnotified", response_model=UnnotifiedListingsResponse)
async def unnotified_listings(
    chat_id: int,
    session: Session = Depends(get_session),
) -> UnnotifiedListingsResponse:
    """Retorna listings não notificados de todos os alertas ativos do usuário."""
    rows = get_unnotified_listings_for_user(session, chat_id)
    items = [
        UnnotifiedListing(**_hydrate_listing(row.listing).model_dump(), alert_id=row.alert_id)
        for row in rows
    ]
    return UnnotifiedListingsResponse(listings=items, total=len(items))

@router.post("/{chat_id}/mark-notified")
async def mark_notified(
    chat_id: int,
    req: MarkNotifiedRequest,
    session: Session = Depends(get_session),
) -> dict:
    """Marca pares (alerta, listing) como notificados."""
    mark_listings_notified_bulk(session, req.pairs)
    return {"status": "ok"}


@router.get("/neighbourhoods", response_model=list)
async def neighbourhoods(
    municipality: str = "Maceió",
    session: Session = Depends(get_session),
) -> list[str]:
    return get_neighbourhoods(session, municipality=municipality)
