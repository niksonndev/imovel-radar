"""Agendamento da coleta diária via APScheduler, no mesmo processo do FastAPI.

Expõe ``start_scheduler`` para o lifespan event do FastAPI.
"""

from .setup import start_scheduler

__all__ = ["start_scheduler"]