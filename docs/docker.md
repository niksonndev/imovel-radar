# Docker — André Assistente Imobiliário (dev local)

O Compose inicia scraper e André no WhatsApp para desenvolvimento. A produção
usa scraper Lambda e assistente WhatsApp no Render (único canal do produto).

## Pré-requisitos

- Docker Engine com Compose v2
- `.env` locais:

  ```bash
  cp apps/scraper/.env.example apps/scraper/.env
  cp apps/whatsapp-bot/.env.example apps/whatsapp-bot/.env
  ```

  O Compose injeta `DATABASE_URL` apontando para o host. O assistente usa a
  sessão persistente do volume `whatsapp_session`.

## Como subir

```bash
docker compose up --build -d
docker compose ps
```

- Scraper: `http://localhost:8000/health`
- André WhatsApp: `http://localhost:10000/health`; QR protegido em `/pair`

## Produção

Deploy do scraper: `.github/workflows/infra-deploy.yml`.

Não há host Compose em produção. O workflow `docker-images.yml` (GHCR) é opcional
(rollback/dev) e **não** alimenta o runtime produtivo.
