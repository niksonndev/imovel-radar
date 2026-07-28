"""Endpoints de alertas: CRUD + matches."""

from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException

from database import get_connection
from database import ensure_user
from database.queries import (
    create_new_alert,
    delete_alert_for_user,
    get_alert_by_id,
    get_alert_for_user,
    get_filtered_listings,
    list_alerts_for_user,
    mark_listings_notified,
    get_listings_by_ids,
    list_active_alerts_with_chat,
)
from shared_models.api_schemas import (
    AlertsListResponse,
    CreateAlertRequest,
    CreateAlertResponse,
    MarkNotifiedRequest,
    MatchesResponse,
)
from shared_models.models import CreateAlertData, HydratedListing, Properties

router = APIRouter(prefix="/alerts", tags=["alerts"])


def _hydrate_listings(rows: list[dict]) -> list[HydratedListing]:
    import json as _json
    result = []
    for row in rows:
        properties_list = (
            _json.loads(row["properties"]) if row["properties"] else []
        )
        for item in properties_list:
            if "real_estate_type" in item:
                item["real_estate_type"] = item["real_estate_type"].split(" - ")[0]
        result.append(
            HydratedListing(
                listId=row["listId"],
                url=row["url"],
                title=row["title"],
                priceValue=row["priceValue"],
                oldPrice=row["oldPrice"],
                municipality=row["municipality"],
                neighbourhood=row["neighbourhood"],
                category=row["category"],
                images=_json.loads(row["images"]),
                properties=[Properties(**p) for p in properties_list],
            )
        )
    return result


@router.post("", response_model=CreateAlertResponse, status_code=201)
async def create_alert(req: CreateAlertRequest) -> CreateAlertResponse:
    """Cria um novo alerta para um usuário."""
    conn = get_connection()
    try:
        internal_user_id = ensure_user(conn, req.user_id)
        data = CreateAlertData(
            user_id=internal_user_id,
            alert_name=req.alert_name,
            min_price=req.min_price,
            max_price=req.max_price,
            neighbourhoods=req.neighbourhoods,
        )
        alert_id = create_new_alert(conn, data)
        conn.commit()
    except Exception:
        conn.rollback()
        raise HTTPException(status_code=500, detail="Falha ao criar alerta")
    finally:
        conn.close()

    return CreateAlertResponse(id=alert_id)


@router.get("", response_model=AlertsListResponse)
async def list_alerts(user_id: int) -> AlertsListResponse:
    """Lista alertas de um usuário (por chat_id do Telegram)."""
    conn = get_connection()
    try:
        internal_user_id = ensure_user(conn, user_id)
        alerts = list_alerts_for_user(conn, internal_user_id)
    finally:
        conn.close()

    return AlertsListResponse(alerts=alerts, total=len(alerts))


@router.get("/{alert_id}", response_model=AlertsListResponse)
async def get_alert(alert_id: int) -> AlertsListResponse:
    """Retorna detalhe de um alerta pelo ID."""
    conn = get_connection()
    try:
        alert = get_alert_by_id(conn, alert_id)
    finally:
        conn.close()

    return AlertsListResponse(alerts=[alert], total=1)


@router.delete("/{alert_id}")
async def delete_alert(alert_id: int, user_id: int) -> dict:
    """Remove um alerta (e seus matches associados)."""
    conn = get_connection()
    try:
        internal_user_id = ensure_user(conn, user_id)
        deleted = delete_alert_for_user(conn, alert_id, internal_user_id)
        conn.commit()
    except Exception:
        conn.rollback()
        raise HTTPException(status_code=500, detail="Falha ao remover alerta")
    finally:
        conn.close()

    if not deleted:
        raise HTTPException(status_code=404, detail="Alerta não encontrado")

    return {"message": "Alerta removido com sucesso"}


@router.get("/{alert_id}/matches", response_model=MatchesResponse)
async def get_matches(alert_id: int) -> MatchesResponse:
    """Retorna matches não notificados para um alerta (hydrated)."""
    conn = get_connection()
    try:
        alert = get_alert_by_id(conn, alert_id)
        neighbourhoods = json.loads(alert["neighbourhoods"])
        filtered = get_filtered_listings(
            conn, alert_id, alert["min_price"], alert["max_price"], neighbourhoods
        )
    finally:
        conn.close()

    if not filtered:
        return MatchesResponse(alert_id=alert_id, matches=[], total=0)

    hydrated = _hydrate_listings(filtered)
    return MatchesResponse(alert_id=alert_id, matches=hydrated, total=len(hydrated))


@router.post("/{alert_id}/matches/notify")
async def mark_notified(alert_id: int, req: MarkNotifiedRequest) -> dict:
    """Marca listings como notificados para um alerta."""
    conn = get_connection()
    try:
        mark_listings_notified(conn, alert_id, req.listing_ids)
        conn.commit()
    except Exception:
        conn.rollback()
        raise HTTPException(status_code=500, detail="Falha ao marcar notificados")
    finally:
        conn.close()

    return {"message": f"{len(req.listing_ids)} listings marcados como notificados"}


@router.get("/active/with-chat", response_model=AlertsListResponse)
async def active_alerts_with_chat() -> AlertsListResponse:
    """Retorna todos os alertas ativos com chat_id (para o bot fazer polling)."""
    conn = get_connection()
    try:
        alerts = list_active_alerts_with_chat(conn)
    finally:
        conn.close()

    return AlertsListResponse(alerts=alerts, total=len(alerts))