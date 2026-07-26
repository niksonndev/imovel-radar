"""Agendamento da coleta diária + notificações, via JobQueue do PTB.

O pacote expõe só ``start_scheduler`` para o ponto de entrada da aplicação
(``main``) poder iniciar o agendamento sem importar ``setup`` ou ``jobs``
diretamente.
"""

from scheduler.setup import start_scheduler

__all__ = ["start_scheduler"]
