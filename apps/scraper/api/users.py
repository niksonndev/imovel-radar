"""Endpoints de usuários: criação e consulta por chat_id."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from shared_models.api_schemas import UserResponse
from sqlmodel import Session

from database import get_session
from database.users import create_user, get_user

router = APIRouter(prefix="/users", tags=["users"])


@router.post("/{chat_id}", response_model=UserResponse, status_code=201)
async def create_user_endpoint(
    chat_id: int,
    session: Session = Depends(get_session),
) -> UserResponse:
    """Cria um usuário com base no Telegram chat_id."""
    user = get_user(session, chat_id)
    if user is None:
        user = create_user(session, chat_id)
        session.commit()

    return UserResponse(chat_id=user.chat_id, created_at=user.created_at)


@router.get("/{chat_id}", response_model=UserResponse)
async def get_user_endpoint(
    chat_id: int,
    session: Session = Depends(get_session),
) -> UserResponse:
    """Retorna um usuário pelo chat_id."""
    user = get_user(session, chat_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")

    return UserResponse(chat_id=user.chat_id, created_at=user.created_at)
