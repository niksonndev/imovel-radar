# imovel-radar 🏠

Bot Telegram para monitorar anúncios de imóveis no OLX Maceió. Realiza scraping diário e notifica usuários quando novos anúncios correspondem aos seus filtros cadastrados.

![Demonstração: `/start`, menu principal e início do fluxo Novo Alerta](assets/demo-aluguel.gif)

## Stack

- **Python 3.11+**
- **Scraper**: `cloudscraper` + `BeautifulSoup4`
- **Bot**: `python-telegram-bot>=21` (polling)
- **Banco**: SQLite via `sqlite3` nativo
- **Agendamento**: cron local → APScheduler (planejado)

## Estrutura

```
imovel-radar/
├── bot/
│   ├── handlers/              # CommandHandlers, roteador de callbacks, texto do wizard
│   │   ├── start_handler.py
│   │   ├── callback_router.py
│   │   └── text_input_handler.py
│   ├── ui/                      # Teclados inline e textos de tela
│   │   ├── keyboards.py
│   │   └── menus.py
│   ├── novo_alerta_wizard.py   # Passos do /novo_alerta (estado em user_data)
│   ├── carousel.py
│   └── setup.py                 # Registra handlers no Application
├── scraper/             # Acesso ao OLX e parsing — não conhece o banco
├── database/            # Conexão, queries e migrations SQLite
├── utils/               # Utilitários neutros (ex.: pricing) — sem bot/scraper/database
├── scripts/             # Utilitários de debug
├── main.py              # Entrypoint
└── config.py            # Constantes e variáveis de ambiente
```

## Fluxo principal

```
cron → main.py → scraper.coletar() → database.upsert_listing()
                                    → database.match_alertas() → bot.notificar()

get_filtered_listings — retorna tudo que bate com o alert
get_unnotified_matches_for_alert — filtra o que já foi notificado via alert_matches
Bot envia o carousel com o que sobrou
Insere na alert_matches os que foram notificados agora
```

## Comandos do bot

| Comando        | Descrição                                     | Status |
| -------------- | --------------------------------------------- | ------ |
| `/start`       | Boas-vindas e menu principal                  | ✅     |
| `/novo_alerta` | Wizard para cadastrar filtro de monitoramento | ✅     |
| `/ajuda`       | Lista de comandos disponíveis                 | ✅     |

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
- `utils/` é camada neutra: não importa `bot/`, `scraper/` nem `database/`; use para código compartilhado (ex.: `utils.pricing`)
- Handlers registrados em `bot/setup.py`, nunca em `main.py`
- Logs via `logging`, nunca `print()` em produção
- Variáveis sensíveis sempre via `.env`, nunca hardcoded
