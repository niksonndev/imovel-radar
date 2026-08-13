# syntax=docker/dockerfile:1
#
# Bot — Imóvel Radar (python-telegram-bot)
# Build context: raiz do monorepo (docker build . -f apps/bot/Dockerfile)
# O contexto inclui packages/shared-models (path dependency editável do uv).

FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

ENV PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_NO_DEV=1

WORKDIR /app

# Usuário não-root (padrão do exemplo oficial astral-sh/uv)
RUN groupadd --system --gid 999 nonroot \
 && useradd --system --gid 999 --uid 999 --create-home nonroot

# Camada de dependências (cache) — path dep shared-models + manifest
COPY packages/shared-models /app/packages/shared-models
COPY apps/bot/pyproject.toml apps/bot/uv.lock /app/apps/bot/

WORKDIR /app/apps/bot
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

# Código-fonte (invalida só quando apps/bot muda; .dockerignore trima caches/venv/env)
COPY apps/bot /app/apps/bot

# Diretório da persistência do PicklePersistence — /data (volume em compose)
RUN mkdir -p /data && chown -R nonroot:nonroot /app /data

# O venv do projeto é criado por `uv sync` em <workdir>/.venv
ENV PATH="/app/apps/bot/.venv/bin:$PATH"
ENTRYPOINT []

USER nonroot

CMD ["python", "main.py"]
