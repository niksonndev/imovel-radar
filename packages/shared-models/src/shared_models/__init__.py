"""Schemas Pydantic compartilhados entre scraper e bot do Imóvel Radar."""

from .api_schemas import (
    AlertsListResponse,
    CreateAlertRequest,
    CreateAlertResponse,
    MarkNotifiedRequest,
    MatchesResponse,
    UnnotifiedListing,
)
from .models import (
    Alert,
    Listing,
    Properties,
)
from .utils import format_brl, money_to_int

__all__ = [
    "Alert",
    "AlertsListResponse",
    "CreateAlertRequest",
    "CreateAlertResponse",
    "UnnotifiedListing",
    "Listing",
    "MarkNotifiedRequest",
    "MatchesResponse",
    "Properties",
    "format_brl",
    "money_to_int",
]