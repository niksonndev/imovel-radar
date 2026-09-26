# Imóvel Radar — Social Bot (Instagram & TikTok)

Bot de **comentários** (webhook em produção) + **publicação local** de foto/vídeo pelo terminal. Não gera conteúdo.

## Deploy (só respostas)

`pnpm --filter instagram-bot start` sobe HTTP em `0.0.0.0:$PORT`:

- `GET /health`
- `GET|POST /webhook` — Meta (comentários Instagram)
- `GET|POST /webhook/tiktok` — eventos TikTok

Não há endpoint de geração ou publicação de mídia.

## Publicar pelo terminal (máquina local)

No diretório `apps/instagram-bot`, com `.env` (`INSTAGRAM_MODE=LIVE` para postar de verdade):

```bash
# Foto
pnpm run publish -- --file ./minha-foto.jpg --caption "Legenda"

# Carrossel
pnpm run publish -- --file ./1.jpg --file ./2.jpg --caption "Carrossel"

# Reels / vídeo
pnpm run publish -- --file ./video.mp4 --caption "Reel"

# TikTok
pnpm run publish -- --platform tiktok --file ./video.mp4 --caption "TikTok"

# Já hospedada
pnpm run publish -- --url https://cdn.exemplo.com/foto.jpg --caption "..."
```

Vídeo no Instagram com **Facebook Login** (`GRAPH_API_HOST=graph.facebook.com`) sobe o arquivo direto (rupload). Com **Instagram Login** (`graph.instagram.com`), foto e vídeo precisam de HTTPS público: instale `cloudflared` ou defina `PUBLISH_BASE_URL` para um túnel na porta `MEDIA_PORT`.

TikTok vídeo usa `FILE_UPLOAD` local. Foto no TikTok LIVE também precisa de URL pública.

## Comentários e analytics (CLI)

```bash
pnpm run comments:process
pnpm run analytics:report
pnpm run mock:simulate-comment
```

## Testes

```bash
pnpm --filter instagram-bot test
```
