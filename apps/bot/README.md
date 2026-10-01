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

## Limpeza de dados

Só depois que o envio terminar sem falhas, faça a prévia agregada:

```bash
uv run --project . --group dev python delete_telegram_data.py
```

Confira as contagens. Para executar, informe exatamente a contagem de usuários
Telegram mostrada na prévia:

```bash
uv run --project . --group dev python delete_telegram_data.py --execute --confirm-users <quantidade>
```

O comando recusa bancos locais e exclui apenas linhas relacionadas a
`users.channel = 'telegram'`; não altera usuários WhatsApp. Migrations e tabelas
compartilhadas permanecem até uma revisão separada.
