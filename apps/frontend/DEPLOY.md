# Deploy no Vercel — Frontend (Next.js)

Este documento lista os passos **manuais** necessários para fazer o deploy do frontend no Vercel.

> ⚠️ A conexão com a conta Vercel **não** é automatizada. Siga os passos abaixo.

---

## 1. Conectar o repositório no Vercel

1. Acesse [vercel.com/new](https://vercel.com/new)
2. Importe o repositório `niksonndev/imovel-radar`
3. Configure o **Root Directory** como `apps/frontend`
4. Framework preset: **Next.js** (detectado automaticamente)
5. Build command: `cd ../.. && pnpm run build` (ou use `turbo run build` — o Vercel detecta o `turbo.json` na raiz)
   - **Alternativa**: deixar o build command padrão do Vercel (`next build`) e configurar `vercel.json` com `"buildCommand": "pnpm run build"` se necessário
6. Output directory: `.next` (padrão)

---

## 2. Variáveis de ambiente

Defina no Vercel (Project Settings → Environment Variables):

| Nome                     | Descrição                                           |
| ------------------------ | --------------------------------------------------- |
| `NEXT_PUBLIC_API_URL`    | URL base da API do backend (ex.: `https://api.exemplo.com`) |

> O backend atualmente **não expõe uma API HTTP**. Assim que uma API for implementada, defina esta variável.

---

## 3. Domínio customizado (opcional)

1. Vá em Project Settings → Domains
2. Adicione seu domínio e siga as instruções de DNS (aponte para `cname.vercel-dns.com`)

---

## 4. Deploy automático

- O Vercel faz deploy automático a cada push na branch `main`
- Para deploy manual: `vercel --prod` (requer Vercel CLI instalada globalmente)

---

## Notas

- O `packageManager` no root `package.json` está configurado como `pnpm@10.33.2` — o Vercel usará pnpm automaticamente
- O Next.js está na raiz de `apps/frontend` — certifique-se de que o Root Directory está apontado corretamente
- O backend **não** é deployado no Vercel — ele roda em uma VM Oracle separada