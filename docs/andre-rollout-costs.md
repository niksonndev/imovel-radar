# André Assistente Imobiliário — custos e QA

Atualizado em 01/10/2026. Pagamentos não estão disponíveis. O atendimento é pelo WhatsApp; o Telegram foi encerrado em 01/10/2026 e os dados do canal foram removidos. O texto legal público é um rascunho de produto, não parecer jurídico.

## Recursos do assistente

| Recurso | WhatsApp (`apps/whatsapp-bot`) |
| --- | --- |
| Conversa por linguagem natural | Function-calling OpenAI; fallback determinístico |
| Memória curta | 6 trocas, TTL padrão 4h, na sessão PostgreSQL |
| Criação de alerta | Critérios acumulados na sessão; confirmação numerada; dedup e cap transacional |
| Botões | `quick_reply` (até 3) no menu, na confirmação do alerta e na remoção; o texto numerado segue no corpo como fallback |
| Remoção | Confirmação numerada; propriedade limitada ao `chat_id` WhatsApp |
| Mercado | Snapshot recente; média e preço/m²; disclaimer de preço pedido |
| Áudio de entrada | Mídia descriptografada pela biblioteca → Whisper, com limite e quota |
| Privacidade | `privacidade`, `excluir dados`; exclusão da conta WhatsApp e dados associados |
| Pagamentos | Pix e cartão via Mercado Pago Checkout Pro (R$ 19,90/1 mês e R$ 99,99/6 meses). Inativo enquanto `MP_ACCESS_TOKEN` não existir; trial por e-mail continua |

Os limites de criação de alertas e watchlist são validados no banco. Quotas padrão de IA são limites operacionais configuráveis, não benefícios prometidos em plano: Free 50 mensagens/5 áudios por dia; Pro 300 mensagens/30 áudios. Áudio limitado a 120 segundos e 20 MiB. A memória não é uma transcrição completa nem contexto permanente.

## Custo variável: estimativa

A tabela oficial consultada do [OpenAI API Pricing](https://developers.openai.com/api/docs/pricing/) informa para `gpt-5.4-mini` Standard $0,75/1M tokens de entrada ($0,075/1M em cache automático de prefixo) e $4,50/1M tokens de saída; Whisper $0,006/minuto. O modelo substituiu o `gpt-4o-mini` (US$ 0,15/1M entrada, US$ 0,60/1M saída) em outubro de 2026 por confiabilidade de function calling: o antigo deixava de emitir `create_alert` em pedidos de confirmação e confundia bairro com município na extração. Os valores são USD e podem mudar; verificar novamente no dia do lançamento. A instrumentação grava tokens totais/entrada/saída e minutos/segundos de áudio agregados por usuário/dia, com alerta operacional configurável. Não registra conteúdo em telemetria.

Exemplo reproduzível, não previsão: supondo 1.500 tokens de entrada + 100 de saída por turno, cada turno custa aproximadamente `1500 × 0,75/1.000.000 + 100 × 4,50/1.000.000 = US$ 0,001575`.

- Free no teto diário: 50 turnos × 30 dias = 1.500 turnos, cerca de US$ 2,36/mês em texto.
- Se todos os 5 áudios/dia durarem 2 minutos: 300 minutos/mês × US$ 0,006 = US$ 1,80; total ilustrativo de IA até US$ 4,16 por usuário/mês.
- Pro no teto diário: 300 turnos × 30 dias = 9.000 turnos, cerca de US$ 14,18/mês em texto; 30 áudios/dia × 2 minutos × 30 dias = 1.800 minutos, US$ 10,80; total ilustrativo de IA até US$ 24,98 por usuário/mês.

O exemplo inclui os turnos de áudio também no volume de texto e acrescenta a transcrição. Não inclui falas mais longas, contexto/tokenização real, extrações de outros fluxos, retries, imposto, spread cambial, tráfego WhatsApp, Render, suporte nem margem. A memória de seis trocas e o prompt do sistema podem elevar tokens de entrada; medir p50/p95 real antes de decidir preço/caps. Medição em 03/10/2026 com o prompt de sistema e as tools de produção, turno isolado e histórico vazio: 1.094–1.178 tokens de entrada e 14–135 de saída, média de US$ 0,001058 por turno — US$ 1,59 (1.500 turnos) e US$ 9,52 (9.000 turnos) por mês, abaixo do exemplo porque a entrada medida ficou perto de 1.170 tokens, não 1.500. É possível estimar custo por usuário com os contadores `assistant_usage` / itens `usage#YYYY-MM-DD` e tarifas vigentes do modelo.

Neon publica no [preçário oficial](https://neon.com/pricing) Free com 100 CU-h/projeto e 0,5 GB; Launch a US$ 0,106/CU-h e armazenamento a US$ 0,35/GB-mês (valores consultados em 29/09/2026). Como Postgres é compartilhado com scraper e outros serviços, não atribuir toda a conta ao André: estime o incremento com CPU/queries/armazenamento medidos e plano real.

Para Lambda, medir duração, memória, arquitetura, região e requests do webhook e aplicar o [calculador/preçário AWS](https://aws.amazon.com/lambda/pricing/). Não foi incluído um valor fixo: deploy atual pode ter tráfego de EventBridge e serviços compartilhados, e o extrato da conta é a fonte para custo marginal.

## Cobrança do Radar Pro (Mercado Pago)

Não existe checkout dentro do WhatsApp para empresa no Brasil: a Meta encerrou o pagamento por cartão para PJ em 15/01/2026 e o caminho é Pix/link. O desenho implementado:

1. `pro` (ou `assinar`) mostra os dois planos; a escolha cria a linha em `pagamento` e uma preferência no Mercado Pago (`/checkout/preferences`), devolvendo o link do checkout hospedado — Pix e cartão na mesma página.
2. O link vai no **corpo** da mensagem (botão `cta_url` é recusado pelo servidor), e o bot nunca pede dado de cartão no chat.
3. O webhook `POST /webhook/mercadopago` valida a assinatura `x-signature` (HMAC-SHA256 com `MP_WEBHOOK_SECRET`) e **confirma o pagamento em `GET /v1/payments/{id}`** — a notificação sozinha não é prova de pagamento, então sem essa segunda chamada um POST inventado viraria assinatura grátis.
4. A ativação é um `UPDATE pagamento ... WHERE status = 'pendente' RETURNING` na mesma transação que estende `users.pro_until` (somando ao que resta). Webhook repetido não estende duas vezes.
5. `já paguei` reconfere pela API (`/v1/payments/search?external_reference=...`): cobre webhook perdido durante um deploy.

Para ligar a cobrança: [ ] migration `0014_pagamentos` aplicada; [ ] conta PJ no Mercado Pago e credenciais no painel (produção ≠ teste); [ ] `MP_ACCESS_TOKEN` e `MP_WEBHOOK_SECRET` no serviço; [ ] `/termos` e `/privacidade` atualizados com cobrança, reembolso e cancelamento; [ ] preço/limite conferidos contra o custo real do assistente.

## Gates antes de vender

- [ ] Definir preço, margem mínima e cap de consumo após 30 dias de dados reais; os cenários acima são estimativas, não preços publicados.
- [ ] Escolher caps diários Free/Pro e limites de tamanho/duração com base em margem e atendimento; publicar somente o que estiver ativo.
- [ ] Aplicar `apps/scraper/alembic/versions/0013_assistant_usage.py` antes do deploy do assistente WhatsApp.
- [ ] Configurar `OPENAI_API_KEY`, `LLM_PROVIDER=openai`, `PUBLIC_SITE_URL`; conferir `ASSISTANT_*_PER_DAY`, `ASSISTANT_MAX_AUDIO_*` e `ASSISTANT_DAILY_TOKEN_ALERT` no runtime.
- [ ] Configurar teto/alertas de gasto no projeto OpenAI e alertas de gasto Neon/infra. A quota do bot não substitui billing hard-stop do provedor.
- [ ] Só anunciar planos pagos depois de implementar cobrança e atualizar preço, termos e política de privacidade.
- [ ] Revisar `/privacidade` e `/termos` com assessoria, confirmar controlador, base legal, contato do titular, prazos e retenções com operação real. As páginas não substituem essa revisão.
- [ ] Definir `SUPPORT_URL` e `NEXT_PUBLIC_SUPPORT_URL` reais para encaminhamento humano de pagamento/reclamação; se não houver canal, não anunciar suporte humano disponível.
- [ ] Verificar que CTAs e respostas sociais abrem `https://wa.me/5582993345293`.
- [ ] Confirmar os dados de preços/m² e cobertura contra snapshot e scraper. Não anunciar cidade/bairro sem coleta confiável.
- [ ] Rodar migrations, `cargo test` em `apps/whatsapp-bot` e lint/testes do frontend.

## QA manual pré-release

1. OpenAI habilitada: “quero apto até 2 mil” → perguntar apenas cidade se ela faltar; resposta seguinte preenche a mesma sessão; mostrar resumo e não gravar até confirmação.
2. Preço entre R$ 20 mil e R$ 50 mil sem tipo → perguntar aluguel/venda; cidade não coberta → informar cobertura atual.
3. Alerta equivalente e cap Free atingido → informar duplicidade/limite sem gravar; repetir chamadas simultâneas e verificar cap no banco.
4. Remover por nome com um e vários candidatos → confirmar sempre; cancelar; botão/estado antigo não pode remover alerta de outro usuário.
5. Mercado sem snapshot, sem cidade/tipo, bairro não ranqueado, média e m² → sem inventar dados; todo número traz “Preço pedido no OLX; valor pode mudar e a negociação é com o anunciante.”
6. Áudio curto válido, acima de 120 s, acima de 20 MiB, MIME inválido, download falhando, whisper indisponível, cota esgotada, áudio view-once e voz em wizard.
7. Free vs Pro trial, Pro expirado, quotas de áudio/texto, token threshold e downgrade; confirmar entitlement no servidor.
8. `excluir dados` → confirmar, cancelar e falha Postgres; conferir alerts, matches, watches, e-mail, sessão, histórico e contadores.
9. Instruções maliciosas no texto/áudio, pedido de dados de terceiros, pagamento e assunto não imobiliário → recusa/redirecionamento sem vazamento.
10. Botões: menu, confirmação do alerta e remoção renderizam como botões e o toque executa a mesma ação do número; testar em Android e iOS e conferir que o texto numerado funciona quando os botões não renderizam.
11. Usar mensagens reais do WhatsApp em staging, revisar legibilidade, latência, fallback de texto e consistência da ajuda.

## Rollback

A migration adiciona somente tabela e colunas de telemetria; código antigo pode ignorá-la, mas novos bots precisam dela. Faça backup e confirme nenhum processo antigo usa os novos estados persistidos antes de rollback. Para desligar IA/áudio, configurar `LLM_PROVIDER=mock`; comandos, alertas, watchlist e wizard continuam disponíveis por caminhos determinísticos.
