# Frontend — Imóvel Radar

Landing page estática (SSG) do Imóvel Radar. O objetivo é uma única ação de conversão: levar o visitante para o bot do Telegram.

## Stack

- **Next.js 16** (App Router) com `output: "export"` — build 100% estático em `out/`
- **Tailwind CSS v4** com tokens do design system Bold (definidos em `src/app/globals.css`)
- **shadcn/ui** (style `base-nova`) + Base UI + lucide-react
- Fontes: Archivo Black (headings), Inter (body) e JetBrains Mono (mono/caps), via `next/font/google`
- Testes de acessibilidade com **Playwright + axe-core**

## Comandos

Este app faz parte de um monorepo Turborepo (pnpm). Da raiz do repositório:

```bash
pnpm run dev     # dev server em http://localhost:3000
pnpm run build   # build estático (saída em apps/frontend/out/)
pnpm run lint    # eslint + tsc --noEmit
pnpm run test    # testes de acessibilidade (builda e serve out/ automaticamente)
```

Ou diretamente em `apps/frontend/`: `pnpm dev`, `pnpm build`, `pnpm lint`, `pnpm test:a11y`.

## Estrutura

```
src/
├── app/
│   ├── layout.tsx           # fontes, metadata global, viewport
│   ├── page.tsx             # composição das seções da landing
│   ├── globals.css          # tokens do tema (Bold design system)
│   ├── robots.ts            # robots.txt gerado no build
│   ├── sitemap.ts           # sitemap.xml gerado no build
│   └── opengraph-image.tsx  # imagem OG gerada no build
├── components/
│   ├── hero-section.tsx     # seções da landing (server components)
│   ├── ...
│   └── ui/                  # componentes shadcn/ui
├── content/
│   └── page-content.ts      # TODO o copy da página — edite aqui
└── lib/
    ├── site.ts             # SITE_URL (env), SITE_NAME e SITE_DESCRIPTION
    └── utils.ts            # cn() e helpers
tests/
└── accessibility/           # specs Playwright + axe (contraste, teclado, reflow)
```

## Editar o conteúdo

Todo o texto da landing vive em [`src/content/page-content.ts`](src/content/page-content.ts). Alterar o copy **não exige mudanças nos componentes**.

A URL do bot do Telegram também está nesse arquivo (`TELEGRAM_BOT_URL`).

## Deploy

Veja [DEPLOY.md](DEPLOY.md) para os passos manuais de deploy na Vercel.
