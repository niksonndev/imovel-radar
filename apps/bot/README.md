# Bot — Imóvel Radar

Cliente "dumb" da API do Scraper. Não acessa banco de dados nem implementa
lógica de negócio — apenas traduz conversas do Telegram em chamadas HTTP.

## Fluxos

### `/novo_alerta` — Wizard de criação

1. Usuário escolhe faixa de preço (preset ou personalizado)
2. Seleciona bairros (multi-seleção com paginação)
3. Define nome do alerta
4. Confirma → `POST /alerts` → `GET /alerts/{id}/matches` → carrossel

### "Meus Alertas"

- Listagem: `GET /alerts?user_id=chat_id`
- Detalhe: `GET /alerts/{id}`
- Remoção: `DELETE /alerts/{id}`

### Carrossel de anúncios

- Navegação Anterior/Próximo via `GET /listings?ids=1,2,3`

## Polling de matches

A cada **1 hora**, o bot consulta `GET /alerts/active/with-chat` e para cada
alerta ativo busca `GET /alerts/{id}/matches`. Se houver matches, envia
carrossel e marca como notificados via `POST /alerts/{id}/matches/notify`.

## Configuração

Variáveis de ambiente (`.env`):

```
TELEGRAM_BOT_TOKEN=123456:ABC-your-bot-token
ADMIN_CHAT_ID=123456789
SCRAPER_API_URL=http://localhost:8000
LOG_LEVEL=INFO
```

## Como rodar

```bash
cd apps/bot
uv pip install -e ../../packages/shared-models
uv sync
# configure .env
uv run python main.py
```

## Arquitetura

```
apps/bot/
├── main.py              # PTB Application + polling setup
├── config.py            # Variáveis de ambiente
├── models.py            # CustomContext, UserData, wizard types
├── handlers/            # Manipuladores de comandos/UI
│   ├── api_client.py    # httpx client tipado para o scraper
│   ├── carousel.py      # Navegação de anúncios
│   ├── create_new_alert.py  # Wizard de criação
│   ├── hydrator.py      # Transformação de dados
│   ├── meus_alertas.py  # CRUD de alertas
│   ├── setup.py         # Registro de handlers
│   └── ui/              # Textos e teclados
└── jobs/                # Jobs agendados
    └── polling_job.py   # Polling de matches (1h)