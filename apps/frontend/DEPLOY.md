# Deploy manual — Vercel

O frontend é um build estático (`output: "export"`), então qualquer host de arquivos estáticos funciona. Abaixo, os passos manuais na Vercel.

## 1. Importar o projeto

1. Acesse [vercel.com/new](https://vercel.com/new) e importe o repositório.
2. Configure o **Root Directory** como `apps/frontend`.
3. Framework preset: **Next.js** (a Vercel detecta automaticamente).

> Alternativa via CLI: `pnpm dlx vercel --cwd apps/frontend`

## 2. Variáveis de ambiente

**Nenhuma variável é obrigatória.** Em produção na Vercel, a URL pública do site é resolvida automaticamente a partir das variáveis de sistema (`VERCEL_PROJECT_PRODUCTION_URL` → `VERCEL_URL`), disponíveis em todos os planos. Certifique-se apenas de que **Settings → Environment Variables → "Enable access to System Environment Variables"** está marcado (padrão).

| Variável | Obrigatória | Descrição |
| --- | --- | --- |
| `NEXT_PUBLIC_SITE_URL` | não (opcional) | Sobrepõe a URL detectada automaticamente. Use apenas se o site tiver um domínio próprio (ex.: `https://imovelradar.com.br`). Usada em canonical, Open Graph, sitemap e robots. O build só **falha** em produção se nem essa variável nem as variáveis de sistema da Vercel estiverem disponíveis; fora da Vercel (dev/build local), um fallback é usado com aviso no log. |

## 3. Build

- Build command: `pnpm build` (herdado do Turborepo) ou `next build`
- Output: estático em `out/`

## 4. Pós-deploy — checklist

- [ ] `/robots.txt` apontando para o sitemap correto (usa a URL pública resolvida)
- [ ] `/sitemap.xml` com a URL de produção
- [ ] OG image renderizando ao compartilhar o link no Telegram/WhatsApp
- [ ] CTA do Telegram abrindo o bot correto
