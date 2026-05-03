from .db import get_connection
from .queries import (
    create_new_alert,
    delete_alert_for_user,
    get_active_alerts_with_chat,
    get_alert_by_id,
    get_alert_for_user,
    get_filtered_listings,
    get_unnotified_matches_for_alert,
    list_alerts_for_user,
    mark_listings_notified,
    upsert_listing,
)
from .schema import create_tables
from .users import ensure_user

__all__ = [
    "create_new_alert",
    "create_tables",
    "delete_alert_for_user",
    "ensure_user",
    "get_active_alerts_with_chat",
    "get_alert_by_id",
    "get_alert_for_user",
    "get_connection",
    "list_alerts_for_user",
    "get_filtered_listings",
    "get_unnotified_matches_for_alert",
    "mark_listings_notified",
    "upsert_listing",
]
