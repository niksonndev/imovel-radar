from __future__ import annotations

from sqlmodel import Session

from .models import User


def create_user(session: Session, chat_id: int) -> User:
    user = User(chat_id=chat_id)
    session.add(user)
    return user


def get_user(session: Session, chat_id: int) -> User | None:
    return session.get(User, chat_id)
