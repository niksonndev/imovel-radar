# Bot Telegram — Alertas OLX Maceió (AL)

Monitora anúncios de imóveis no [OLX](https://www.olx.com.br) para **Maceió, Alagoas**: alertas por filtros, watchlist de preço e notificações no Telegram.

## Requisitos

- Python **3.11+**
- Conta e token de bot no [@BotFather](https://t.me/BotFather)

## Instalação

```bash
cd olx_maceio_bot
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

pip install -r requirements.txt
copy .env.example .env   # ou cp no Linux/macOS
```

Edite `.env` e defina `TELEGRAM_BOT_TOKEN`.

## Execução

```bash
python main.py
```

O SQLite é criado em `data/bot.db` (ou conforme `DATABASE_URL`).

## Comandos (português no bot)

| Comando | Descrição |
|--------|-----------|
| `/start` | Boas-vindas e instruções |
| `/novo_alerta` | Assistente: nome, tipo (apt/casa/terreno/comercial), venda/aluguel, preço, quartos, m², bairros |
| `/meus_alertas` | Lista alertas (id, nome, ativo/pausado) |
| `/pausar_alerta [id]` | Pausar ou reativar |
| `/deletar_alerta [id]` | Apagar alerta |
| `/observar [url]` | Adicionar URL OLX à watchlist |
| `/watchlist` | Listar observados |
| `/remover [id]` | Remover da watchlist |
| `/status` | Intervalos e próximas verificações |
| `/ajuda` | Ajuda completa |
| `/cancelar` | Cancelar wizard |

## Variáveis de ambiente (`.env.example`)

- `TELEGRAM_BOT_TOKEN` — obrigatório  
- `ALERT_CHECK_INTERVAL_MINUTES` — padrão `30`  
- `WATCHLIST_CHECK_INTERVAL_HOURS` — padrão `6`  
- `DATABASE_URL` — padrão SQLite em `./data/bot.db`  
- `SCRAPER_DELAY_MIN` / `SCRAPER_DELAY_MAX` — atraso entre requisições (2–5 s)  

## Comportamento

1. **Alertas** — Monta URLs do tipo  
   `https://www.olx.com.br/imoveis/{venda|aluguel}/{tipo}/estado-al/alagoas/maceio`  
   com filtros (preço `pe`, bairros em `q`). A cada ciclo, compara com anúncios já vistos no banco; **no primeiro ciclo** de cada alerta só grava os IDs (sem flood de mensagens); nos seguintes, notifica só anúncios novos.

2. **Watchlist** — Acessa a página do anúncio, lê preço/título; se mudar o preço ou sumir (404 / indisponível), notifica.

3. **Scraping** — `httpx` + BeautifulSoup, com foco no JSON `__NEXT_DATA__` (Next.js). Se o OLX mudar o front ou bloquear bots, pode ser necessário **Playwright** ou ajustar o parser. Respeite [robots.txt](https://www.olx.com.br/robots.txt) e use intervalos conservadores.

## Estrutura

```
olx_maceio_bot/
├── bot/           # handlers, conversations, keyboards
├── scraper/       # OLXScraper, parser
├── database/      # SQLAlchemy + CRUD
├── scheduler/     # APScheduler
├── config.py
├── main.py
├── requirements.txt
└── .env.example
```

## Aviso legal

Uso educacional/pessoal. O OLX pode alterar HTML/API e restringir scrapers. Cada usuário é responsável pelo uso conforme termos do site.
