from __future__ import annotations

from shared_models.tables import User
from sqlmodel import Session


def create_user(session: Session, chat_id: int) -> User:
    user = User(chat_id=chat_id)
    session.add(user)
    return user


def get_user(session: Session, chat_id: int) -> User | None:
    return session.get(User, chat_id)
