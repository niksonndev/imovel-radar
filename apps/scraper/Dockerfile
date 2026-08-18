# syntax=docker/dockerfile:1
#
# Scraper — Imóvel Radar (FastAPI)
# Build context: raiz do monorepo (docker build . -f apps/scraper/Dockerfile)
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
COPY apps/scraper/pyproject.toml apps/scraper/uv.lock /app/apps/scraper/

WORKDIR /app/apps/scraper
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

# Código-fonte (invalida só quando apps/scraper muda; .dockerignore trima caches/venv/env)
COPY apps/scraper /app/apps/scraper

# O banco é Postgres externo (sem volume local de dados)
RUN chown -R nonroot:nonroot /app

# O venv do projeto é criado por `uv sync` em <workdir>/.venv
ENV PATH="/app/apps/scraper/.venv/bin:$PATH"
ENTRYPOINT []

EXPOSE 8000
USER nonroot

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
