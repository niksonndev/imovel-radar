"""Endpoints de alertas: CRUD + matches."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from shared_models.api_schemas import (
    AlertsListResponse,
    CreateAlertRequest,
    CreateAlertResponse,
)
from shared_models.models import Alert
from sqlmodel import Session

from database import get_session
from database.models import Alert as AlertModel
from database.queries import (
    create_alert,
    delete_alert_for_user,
    get_active_alerts_for_user,
    get_alert_for_user,
    get_alerts_for_user,
)

router = APIRouter(prefix="/alerts", tags=["alerts"])


def _shared_alert(alert: AlertModel) -> Alert:
    """Converte um Alert (SQLModel) para o contrato da API."""
    assert alert.id is not None, "alert vindo do banco deveria sempre ter id"
    assert alert.created_at is not None, "alert vindo do banco deveria sempre ter created_at"
    return Alert(
        id=alert.id,
        chat_id=alert.chat_id,
        alert_name=alert.alert_name,
        min_price=alert.min_price,
        max_price=alert.max_price,
        neighbourhoods=alert.neighbourhoods,
        active=alert.active,
        created_at=alert.created_at,
    )


@router.post("", response_model=CreateAlertResponse, status_code=201)
async def create_alert_endpoint(
    alert: CreateAlertRequest,
    session: Session = Depends(get_session),
) -> CreateAlertResponse:
    """Cria um novo alerta para um usuário."""
    alert_id = create_alert(session, alert)
    session.commit()
    return CreateAlertResponse(id=alert_id)


@router.get("/{chat_id}", response_model=AlertsListResponse)
async def list_alerts(
    chat_id: int,
    session: Session = Depends(get_session),
) -> AlertsListResponse:
    """Lista todos os alertas de um usuário (ativos ou não)."""
    alerts = [_shared_alert(a) for a in get_alerts_for_user(session, chat_id)]
    return AlertsListResponse(alerts=alerts, total=len(alerts))


@router.get("/{chat_id}/active", response_model=AlertsListResponse)
async def list_active_alerts(
    chat_id: int,
    session: Session = Depends(get_session),
) -> AlertsListResponse:
    """Lista apenas os alertas ativos de um usuário."""
    alerts = [_shared_alert(a) for a in get_active_alerts_for_user(session, chat_id)]
    return AlertsListResponse(alerts=alerts, total=len(alerts))


@router.get("/{chat_id}/{alert_id}", response_model=Alert)
async def get_alert(
    chat_id: int,
    alert_id: int,
    session: Session = Depends(get_session),
) -> Alert:
    """Retorna um alerta específico de um usuário."""
    alert = get_alert_for_user(session, alert_id, chat_id)
    if alert is None:
        raise HTTPException(status_code=404, detail="Alerta não encontrado")
    return _shared_alert(alert)


@router.delete("/{chat_id}/{alert_id}")
async def delete_alert(
    chat_id: int,
    alert_id: int,
    session: Session = Depends(get_session),
) -> dict:
    """Remove um alerta (e seus matches associados)."""
    deleted = delete_alert_for_user(session, alert_id, chat_id)
    session.commit()

    if not deleted:
        raise HTTPException(status_code=404, detail="Alerta não encontrado")
    return {"message": "Alerta removido com sucesso"}
