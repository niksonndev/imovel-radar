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
cron (APScheduler) → job_daily()
  → _do_full_scrape()
      → search_all_rent_maceio()       # scraper: busca todas as páginas da OLX
      → extract_listings_from_search_page()  # parser: descarta listings sem foto
      → upsert listings no banco       # INSERT OR REPLACE em listings

  → _notify_new_matches_all_alerts()
      → list_active_alerts_with_chat() # todos os alertas ativos + chat_id do usuário
      → para cada alerta:
          seed_alert_carousel(app, alert_id, chat_id)
            → find_matches_for_alert()     # listings que batem com o alerta e ainda não foram notificados (LEFT JOIN alert_matches IS NULL)
            → hydrate_listing()            # json.loads em images/properties, normaliza real_estate_type
            → send_carousel()              # bot envia carousel ao usuário
            → mark_listings_notified()     # INSERT em alert_matches para não renotificar
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
