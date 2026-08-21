# Deploy manual — Vercel

O frontend é um build estático (`output: "export"`), então qualquer host de arquivos estáticos funciona. Abaixo, os passos manuais na Vercel.

## 1. Importar o projeto

1. Acesse [vercel.com/new](https://vercel.com/new) e importe o repositório.
2. Configure o **Root Directory** como `apps/frontend`.
3. Framework preset: **Next.js** (a Vercel detecta automaticamente).

> Alternativa via CLI: `pnpm dlx vercel --cwd apps/frontend`

## 2. Variáveis de ambiente

| Variável | Obrigatória | Descrição |
| --- | --- | --- |
| `NEXT_PUBLIC_SITE_URL` | sim (produção) | URL pública do site (ex.: `https://imovelradar.com.br`). Usada em canonical, Open Graph, sitemap e robots. O build **falha** se esta variável não estiver definida em deploy de produção na Vercel; em dev/preview, um fallback é usado com aviso no log. |

## 3. Build

- Build command: `pnpm build` (herdado do Turborepo) ou `next build`
- Output: estático em `out/`

## 4. Pós-deploy — checklist

- [ ] `/robots.txt` apontando para o sitemap correto (usa `NEXT_PUBLIC_SITE_URL`)
- [ ] `/sitemap.xml` com a URL de produção
- [ ] OG image renderizando ao compartilhar o link no Telegram/WhatsApp
- [ ] CTA do Telegram abrindo o bot correto
