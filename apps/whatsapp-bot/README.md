# Bot WhatsApp — Imóvel Radar

Cliente WhatsApp Web em Rust ([whatsapp-rust](https://github.com/oxidezap/whatsapp-rust)), sempre ligado. Cobre o mesmo fluxo do bot Telegram: alerta em linguagem natural ou passo a passo, meus alertas, carrossel de matches, watchlist e trial de Radar Pro por e-mail. Não há Telegram Stars.

Cliente não oficial: pode violar os termos da Meta e a conta pode ser suspensa.

## Assistente André

Com `LLM_PROVIDER=openai`, texto e áudio usam function-calling do Chat Completions; sem OpenAI, há fallback determinístico. A conversa mantém até seis trocas por quatro horas e remove padrões comuns de e-mail/CPF/cartão antes de persistir. Criação exige confirmação, remoção sempre exige confirmação e o mercado usa somente o snapshot recente, incluindo o aviso de preço pedido. Áudios de até 120 segundos/20 MiB são transcritos via Whisper quando habilitado.

Quotas padrão por dia: Free 50 mensagens/5 áudios; Pro 300 mensagens/30 áudios. São limites operacionais configuráveis, não benefícios comerciais. O Postgres aplica caps de alertas/watchlist em transação e guarda contagens agregadas de áudio/tokens.

Use `privacidade` para política/termos e `excluir dados` para solicitar exclusão. A exclusão confirmada apaga conta WhatsApp, alertas, matches, anúncios acompanhados, trial por e-mail, sessão e telemetria associada. A política e os termos publicados são textos de produto e devem ser revisados por assessoria jurídica antes de serem considerados documentos finais.

O WhatsApp não oferece Telegram Stars. O Pro neste canal usa somente o fluxo de trial por e-mail existente; não há processamento Pix implementado.

## Como funciona

- Processo único: HTTP (`GET /health`, `GET /pair`) + sessão WhatsApp + notificação diária às 10:00 (America/Maceio), só para `users.channel = 'whatsapp'`.
- Postgres compartilhado (Neon). A migration `0012` cria `channel`, `whatsapp_jid`, a sequence de `chat_id` e `bot_session`.
- Conta WhatsApp não se vincula à conta Telegram.

## Configuração

```bash
cp apps/whatsapp-bot/.env.example apps/whatsapp-bot/.env
```

Rode a migration antes (o scraper aplica no boot, ou `cd apps/scraper && uv run alembic upgrade head`).

## Dev

```bash
cd apps/whatsapp-bot
cargo run
```

No primeiro boot o terminal imprime o QR. Também dá para abrir `http://localhost:10000/pair?token=$PAIR_SECRET`.

Compose, na raiz:

```bash
docker compose up whatsapp-bot
```

## Render

Blueprint em `render.yaml`: web service Docker no plano **free** (instância única, sem disco persistente — `/data` é efêmero). Como a sessão SQLite não sobrevive a deploy/restart, o bot faz backup consistente (`VACUUM INTO`) no Neon a cada 5 min e restaura no boot (`wa_session_backup`) — é isso que dispensa re-parear por QR.

No primeiro deploy, abra `https://<serviço>/pair?token=<PAIR_SECRET>` e escaneie. Nos deploys seguintes a sessão é restaurada do Neon (sem novo QR); há apenas uma breve reconexão, não re-pareamento.

Antes de deployar, aplique todas as migrations Alembic, inclusive `0013_assistant_usage`.

Defina `DATABASE_URL` (Neon pooled), `OPENAI_API_KEY`, `PUBLIC_SITE_URL` e o destino humano real em `SUPPORT_URL`/`NEXT_PUBLIC_SUPPORT_URL` antes de anunciar atendimento. `PAIR_SECRET` é gerado pelo blueprint.

## Testes

```bash
cd apps/whatsapp-bot && cargo test
```
