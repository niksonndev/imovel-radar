# Pacote database: modelos (tabelas) + funções CRUD (acesso ao banco).
# Em Python, pasta com __init__.py vira "módulo" importável: from database import ...

from database.models import Base, User, Alert, SeenListing, WatchedListing
from database.crud import create_engine_and_session, init_db

__all__ = [
    "Base",
    "User",
    "Alert",
    "SeenListing",
    "WatchedListing",
    "create_engine_and_session",
    "init_db",
]
