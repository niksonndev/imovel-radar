# André Assistente Imobiliário — custos e QA

Atualizado em 01/10/2026. Pagamentos não estão disponíveis. O atendimento é pelo WhatsApp; o Telegram foi encerrado em 01/10/2026 e os dados do canal foram removidos. O texto legal público é um rascunho de produto, não parecer jurídico.

## Recursos do assistente

| Recurso | WhatsApp (`apps/whatsapp-bot`) |
| --- | --- |
| Conversa por linguagem natural | Function-calling OpenAI; fallback determinístico |
| Memória curta | 6 trocas, TTL padrão 4h, na sessão PostgreSQL |
| Criação de alerta | Critérios acumulados na sessão; confirmação numerada; dedup e cap transacional |
| Remoção | Confirmação numerada; propriedade limitada ao `chat_id` WhatsApp |
| Mercado | Snapshot recente; média e preço/m²; disclaimer de preço pedido |
| Áudio de entrada | Mídia descriptografada pela biblioteca → Whisper, com limite e quota |
| Privacidade | `privacidade`, `excluir dados`; exclusão da conta WhatsApp e dados associados |
| Pagamentos | Desativados; benefícios de teste dependem de oferta disponível |

Os limites de criação de alertas e watchlist são validados no banco. Quotas padrão de IA são limites operacionais configuráveis, não benefícios prometidos em plano: Free 50 mensagens/5 áudios por dia; Pro 300 mensagens/30 áudios. Áudio limitado a 120 segundos e 20 MiB. A memória não é uma transcrição completa nem contexto permanente.

## Custo variável: estimativa

A tabela oficial consultada do [OpenAI API Pricing](https://developers.openai.com/api/docs/pricing/) informa para `gpt-4o-mini` Standard $0,15/1M tokens de entrada e $0,60/1M tokens de saída; Whisper $0,006/minuto. Os valores são USD e podem mudar; verificar novamente no dia do lançamento. A instrumentação grava tokens totais/entrada/saída e minutos/segundos de áudio agregados por usuário/dia, com alerta operacional configurável. Não registra conteúdo em telemetria.

Exemplo reproduzível, não previsão: supondo 1.500 tokens de entrada + 100 de saída por turno, cada turno custa aproximadamente `1500 × 0,15/1.000.000 + 100 × 0,60/1.000.000 = US$ 0,000285`.

- Free no teto diário: 50 turnos × 30 dias = 1.500 turnos, cerca de US$ 0,43/mês em texto.
- Se todos os 5 áudios/dia durarem 2 minutos: 300 minutos/mês × US$ 0,006 = US$ 1,80; total ilustrativo de IA até US$ 2,23 por usuário/mês.
- Pro no teto diário: 300 turnos × 30 dias = 9.000 turnos, cerca de US$ 2,57/mês em texto; 30 áudios/dia × 2 minutos × 30 dias = 1.800 minutos, US$ 10,80; total ilustrativo de IA até US$ 13,37 por usuário/mês.

O exemplo inclui os turnos de áudio também no volume de texto e acrescenta a transcrição. Não inclui falas mais longas, contexto/tokenização real, extrações de outros fluxos, retries, imposto, spread cambial, tráfego WhatsApp, Render, suporte nem margem. A memória de seis trocas e o prompt do sistema podem elevar tokens de entrada; medir p50/p95 real antes de decidir preço/caps. É possível estimar custo por usuário com os contadores `assistant_usage` / itens `usage#YYYY-MM-DD` e tarifas vigentes do modelo.

Neon publica no [preçário oficial](https://neon.com/pricing) Free com 100 CU-h/projeto e 0,5 GB; Launch a US$ 0,106/CU-h e armazenamento a US$ 0,35/GB-mês (valores consultados em 29/09/2026). Como Postgres é compartilhado com scraper e outros serviços, não atribuir toda a conta ao André: estime o incremento com CPU/queries/armazenamento medidos e plano real.

Para Lambda, medir duração, memória, arquitetura, região e requests do webhook e aplicar o [calculador/preçário AWS](https://aws.amazon.com/lambda/pricing/). Não foi incluído um valor fixo: deploy atual pode ter tráfego de EventBridge e serviços compartilhados, e o extrato da conta é a fonte para custo marginal.

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
10. Usar mensagens reais do WhatsApp em staging, revisar legibilidade, latência, fallback de texto e consistência da ajuda.

## Rollback

A migration adiciona somente tabela e colunas de telemetria; código antigo pode ignorá-la, mas novos bots precisam dela. Faça backup e confirme nenhum processo antigo usa os novos estados persistidos antes de rollback. Para desligar IA/áudio, configurar `LLM_PROVIDER=mock`; comandos, alertas, watchlist e wizard continuam disponíveis por caminhos determinísticos.
