"""Acesso direto da Bot Lambda ao Postgres compartilhado (ADR 0005).

A bot é a dona de ``users``, ``alerts`` e ``alert_matches`` e lê ``listing``
(read-only). Não há mais hop HTTP para o scraper.
"""
