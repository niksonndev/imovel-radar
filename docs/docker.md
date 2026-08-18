# Docker — Imóvel Radar (scraper + bot)

Containerização dos serviços Python do monorepo (`apps/scraper` e `apps/bot`) via
`Dockerfile` + `docker-compose.yml` na raiz.

## Pré-requisitos

- Docker Engine com o plugin **Compose v2** (testado com Docker 29.6.2).
- `.env` locais configurados (o compose injeta via `env_file`, mas não é obrigatório
  o arquivo existir para build):
  ```bash
  cp apps/scraper/.env.example apps/scraper/.env
  cp apps/bot/.env.example apps/bot/.env
  ```
  ⚠️ `apps/bot/.env` precisa de `TELEGRAM_BOT_TOKEN` válido e
  `SCRAPER_API_URL=http://scraper:8000` (o valor `localhost` não funciona no container;
  o compose já sobrescreve isso via `environment`).

## Estrutura

```
├── .dockerignore          # exclui segredos/venv/caches do build context
├── docker-compose.yml     # dev: orquestra scraper + bot (build local)
├── docker-compose.prod.yml# prod: imagens do GHCR (sem build/bind mounts)
├── apps/scraper/Dockerfile
├── apps/bot/Dockerfile
└── .github/workflows/
    └── docker-images.yml  # builda + publica as imagens no GHCR
```

> Os dois `Dockerfile`s têm **build context = raiz do monorepo** porque os apps
> dependem do pacote `packages/shared-models` (path dependency editável do `uv`).
> O bot mantém um volume em `/data` (pickle); o scraper usa Postgres externo via `DATABASE_URL`.

## Como subir

```bash
docker compose up --build -d
docker compose ps        # scraper deve estar "healthy"; bot "Up"
```

- Scraper: `http://localhost:8000` — endpoint de saúde em `GET /health`.
- Bot: conecta ao Telegram via polling (sem porta exposta).

## Persistência

| Serviço  | Volume          | Dados |
|----------|-----------------|-------|
| scraper  | —               | Postgres externo via `DATABASE_URL` (dev: pg-local; prod: Neon) |
| bot      | `bot_state`     | `carousel_state.pickle` (estado PicklePersistence) |

## Comandos úteis

```bash
docker compose logs -f scraper
docker compose logs -f bot
docker compose restart bot
docker compose down          # para (mantém volumes)
docker compose down -v       # para e apaga os volumes (reset total)
```

## Build individual (cache de camadas)

```bash
docker build . -f apps/scraper/Dockerfile -t imovel-radar-scraper
docker build . -f apps/bot/Dockerfile    -t imovel-radar-bot
```

As dependências são sincronizadas em uma camada própria (antes do código-fonte),
então o rebuild só re-instala deps quando `pyproject.toml`/`uv.lock`/`shared-models` mudam.

## Produção (GHCR + GHA)

O workflow [`.github/workflows/docker-images.yml`](../.github/workflows/docker-images.yml)
builda e publica as imagens no **GitHub Container Registry** nas plataformas
`linux/amd64` e `linux/arm64`, nas tags:

- `latest` + sha curto (toda push em `main`)
- `vX.Y.Z` / `vX.Y` (toda tag `v*`)

O `docker-compose.prod.yml` consome essas imagens (não builda nem usa bind mounts de código).

### Pré-requisito de autenticação no host

As imagens posteriores são **privadas** por padrão — o host do deploy precisa logar no GHCR:

```bash
# token com escopo packages:read (PAT ou GITHUB_TOKEN do repo)
echo "$CR_PAT" | docker login ghcr.io -u <github-username> --password-stdin
```

### Deploy

```bash
IMAGE_TAG=v1.2.3 docker compose -f docker-compose.prod.yml pull
IMAGE_TAG=v1.2.3 docker compose -f docker-compose.prod.yml up -d
```

- `IMAGE_TAG` default `.latest` (omitido = última build de `main`).
- O **scraper não expõe porta**: a API fica apenas na rede interna do compose;
  só o bot a alcança via `http://scraper:8000` e o healthcheck (`/health`).
- No primeiro deploy, as `.env` (criadas a partir dos `.env.example`) podem ser
  enviadas como secrets do GHA para o servidor.

## Observações

- **Segredos**: `.env` é excluído do build via `.dockerignore` — nunca vão para a imagem.
- **Usuário não-root**: os containers rodam como `nonroot` (uid/gid 999). O scraper usa
  Postgres externo; só o bot mantém volume local (`/data`).
- **Frontend** (`apps/frontend`, Next.js) fica de fora do compose por ser estático e
  deployado no Vercel.
