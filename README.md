# imovel-radar 🏠

Bot Telegram para monitorar anúncios de imóveis no OLX Maceió. Realiza scraping diário e notifica usuários quando novos anúncios correspondem aos seus filtros cadastrados.

![Demonstração: `/start`, menu principal e início do fluxo Novo Alerta](assets/demo-aluguel.gif)

## Stack

- **Python 3.11+**
- **Scraper**: `cloudscraper` + `BeautifulSoup4`
- **Bot**: `python-telegram-bot>=20` (polling)
- **Banco**: SQLite via `sqlite3` nativo
- **Agendamento**: cron local → APScheduler (planejado)

## Estrutura

```
imovel-radar/
├── bot/
│   ├── handlers.py      # CommandHandlers simples
│   ├── callbacks.py     # CallbackQueryHandlers (menu, carrossel, ações)
│   ├── conversations.py # ConversationHandlers multi-step (/novo_alerta)
│   └── setup.py         # Registra todos os handlers no Application
├── scraper/             # Acesso ao OLX e parsing — não conhece o banco
├── database/            # Conexão, queries e migrations SQLite
├── scripts/             # Utilitários de debug
├── main.py              # Entrypoint
└── config.py            # Constantes e variáveis de ambiente
```

## Fluxo principal

```
cron → main.py → scraper.coletar() → database.upsert_listing()
                                    → database.match_alertas() → bot.notificar()
```

## Comandos do bot

| Comando           | Descrição                                     | Status |
| ----------------- | --------------------------------------------- | ------ |
| `/start`          | Boas-vindas e menu principal                  | ✅     |
| `/novo_alerta`    | Wizard para cadastrar filtro de monitoramento | ✅     |
| `/ajuda`          | Lista de comandos disponíveis                 | ✅     |
| `/status`         | Próximas execuções do scheduler               | ✅     |
| `/meus_alertas`   | Listar alertas cadastrados                    | 🚧     |
| `/pausar_alerta`  | Pausar/reativar alerta por id                 | 🚧     |
| `/deletar_alerta` | Apagar alerta por id                          | 🚧     |
| `/observar`       | Monitorar URL específica                      | 🚧     |
| `/watchlist`      | Listar URLs observadas                        | 🚧     |
| `/remover`        | Remover da watchlist por id                   | 🚧     |

## Configuração

```bash
cp .env.example .env
# editar .env com TELEGRAM_BOT_TOKEN e demais variáveis
pip install -r requirements.txt
python main.py
```

## Convenções

- `scraper/` não importa nada de `database/` ou `bot/`
- `bot/` não importa nada de `scraper/`
- Handlers registrados em `bot/setup.py`, nunca em `main.py`
- Logs via `logging`, nunca `print()` em produção
- Variáveis sensíveis sempre via `.env`, nunca hardcoded
