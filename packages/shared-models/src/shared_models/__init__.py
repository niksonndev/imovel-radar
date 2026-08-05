"""Schemas Pydantic compartilhados entre scraper e bot do Imóvel Radar."""

from .api_schemas import (
    AlertsListResponse,
    CreateAlertRequest,
    CreateAlertResponse,
    HealthResponse,
    ListingsByIdsRequest,
    ListingsListHydratedResponse,
    ListingsListResponse,
    MarkNotifiedRequest,
    MatchesResponse,
    NeighbourhoodsResponse,
)
from .models import (
    Alert,
    CreateAlertData,
    HydratedListing,
    Listing,
    Properties,
)
from .utils import format_brl, money_to_int

__all__ = [
    "Alert",
    "AlertsListResponse",
    "CreateAlertData",
    "CreateAlertRequest",
    "CreateAlertResponse",
    "HealthResponse",
    "HydratedListing",
    "ListingsByIdsRequest",
    "ListingsListHydratedResponse",
    "ListingsListResponse",
    "Listing",
    "MarkNotifiedRequest",
    "MatchesResponse",
    "NeighbourhoodsResponse",
    "Properties",
    "format_brl",
    "money_to_int",
]