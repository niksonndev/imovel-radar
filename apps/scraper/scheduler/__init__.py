"""Coleção diária do OLX.

A coleta é disparada pelo EventBridge (Lambda) ou manualmente — não há mais
scheduler em processo (ADR 0004).
"""

from .jobs import job_daily

__all__ = ["job_daily"]
