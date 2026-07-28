---
paths:
  - "apps/frontend/**"
---

# Frontend Guidelines (Next.js 16)

# This is NOT the Next.js you know

Before doing any work in this directory:
1. Check the relevant doc in `apps/frontend/node_modules/next/dist/docs/`
   before writing any code — it is the source of truth, not your training data.
2. Pay attention to deprecation notices.
3. Use the `context` MCP for React and Tailwind CSS documentation — do not rely on training data for API details.
4. Use the `shadcn` MCP to browse, search, and install shadcn/ui components — do not hand-write component code from memory. Check `components.json` at the project root first; it is already configured (style: base-nova, aliases under `@/components`, `@/lib`, etc.) — do not re-run init/setup steps.

## Stack
- Next.js 16, App Router, SSG (static output — no server actions, no dynamic fetch at request time)
- shadcn/ui + Tailwind CSS
- Single conversion action: CTA linking to an external Telegram bot (no form, no in-house lead capture)
- No client-side state management (not needed — static page)