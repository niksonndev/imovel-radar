# Telegram legado — encerramento temporário

Este app não é mais um canal de produto. Ele permanece somente para comunicar
o encerramento aos usuários e será removido após o envio e a limpeza de dados.

## Prévia segura

No diretório `apps/bot`, com a conexão de produção configurada:

```bash
uv run --project . --group dev python send_final_notice.py
```

O modo padrão mostra o texto e a contagem, sem exibir IDs nem enviar mensagens.
Não use uma base local para o anúncio.

## Envio explícito

Depois de conferir a prévia e a quantidade, execute com o valor exato mostrado:

```bash
uv run --project . --group dev python send_final_notice.py --send --confirm-count <quantidade>
```

O envio é bloqueado se a lista estiver vazia. O teste está em
`tests/test_final_notice.py`.
