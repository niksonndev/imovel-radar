# Imovel Radar — Bot Telegram (OLX Maceió)

Monitora anúncios de imóveis no [OLX](https://www.olx.com.br) em **Maceió/AL** e avisa no Telegram: **alertas por filtros** e **watchlist de preço**.

---

## Se você vem do JavaScript (mapa mental)

| JS / Node                      | Este projeto (Python)                                                |
| ------------------------------ | -------------------------------------------------------------------- |
| `npm install`                  | `py -m pip install -r requirements.txt`                              |
| `package.json` (lista de deps) | `requirements.txt`                                                   |
| `node index.js`                | `py main.py`                                                         |
| `.env` com `process.env`       | `.env` + biblioteca `python-dotenv` → `os.getenv` em `config.py`     |
| Express rotas                  | Comandos Telegram (`/start`, `/novo_alerta`, …) em `bot/handlers.py` |
| `setInterval` / cron           | **APScheduler** em `scheduler/jobs.py` (a cada X minutos/horas)      |
| Mongo/SQLite via driver        | **SQLAlchemy** + SQLite em `database/`                               |
| `fetch` + parse HTML           | **Playwright** + **BeautifulSoup** em `scraper/`                     |

O programa **não é um servidor HTTP** que você abre no browser: é um **processo que fica rodando** falando com a API do Telegram (long polling). Enquanto o terminal estiver com `py main.py` ativo, o bot responde.

---

## O que o projeto faz (fluxo)

1. `**main.py`\*\* — Ponto de entrada. Sobe o bot, registra comandos e, ao iniciar, abre o banco, o scraper e o agendador.
2. `**config.py**` — Lê `.env` (token, intervalos, caminho do banco). Sem `TELEGRAM_BOT_TOKEN` o app nem sobe.
3. `**bot/handlers.py**` — Cada comando do Telegram (`/start`, `/observar`, …).
4. `**bot/conversations.py**` — Assistente passo a passo do `/novo_alerta` (várias mensagens em sequência).
5. `**scraper/**` — Baixa páginas do OLX, monta URL de busca Maceió, extrai lista de anúncios (HTML + JSON embutido).
6. `**database/**` — Usuários, alertas, “já vistos”, watchlist (SQLite em `data/bot.db`).
7. `**scheduler/jobs.py**` — De tempo em tempo: (a) busca anúncios novos para cada alerta e manda mensagem; (b) confere preço dos links da watchlist.

**Primeiro ciclo de um alerta:** só grava os IDs atuais (sem spammar). **Ciclos seguintes:** só notifica anúncio **novo**.

---

## Requisitos

- Python **3.11+**
- Token do [@BotFather](https://t.me/BotFather)

---

## Instalação e execução (raiz do repo `imovel-radar`)

Abra o terminal **na pasta do projeto** (onde estão `main.py` e `requirements.txt`).

```bash
py -m venv .venv
.venv\Scripts\activate
py -m pip install --upgrade pip
py -m pip install -r requirements.txt
playwright install chromium
```

Crie o `.env` (pode copiar o exemplo):

```bash
copy .env.example .env
```

Edite `.env` e coloque seu token:

```env
TELEGRAM_BOT_TOKEN=123456:ABC-seu-token-aqui
```

**Rodar o bot:**

```bash
py main.py
```

Deixe essa janela aberta. Pare com **Ctrl+C**.

O SQLite fica em `**data/bot.db`\*\* (criado automaticamente).

---

## Comandos no Telegram

| Comando                | O que faz                                                             |
| ---------------------- | --------------------------------------------------------------------- |
| `/start`               | Boas-vindas + menu inline (teclas para ações)                   |
| `/novo_alerta`         | Criar alerta (nome, tipo, venda/aluguel, preço, quartos, m², bairros) |
| `/meus_alertas`        | Listar alertas                                                        |
| `/pausar_alerta [id]`  | Pausar/reativar                                                       |
| `/deletar_alerta [id]` | Apagar alerta                                                         |
| `/observar [url]`      | Monitorar um anúncio (preço / sumiu)                                  |
| `/watchlist`           | Ver observados                                                        |
| `/remover [id]`        | Tirar da watchlist                                                    |
| `/status`              | Próximas verificações agendadas                                       |
| `/ajuda`               | Ajuda                                                                 |
| `/cancelar`            | Cancelar wizard                                                       |

---

## Estrutura de pastas

```
imovel-radar/
├── main.py              # ← você roda isso
├── config.py          # .env + constantes
├── requirements.txt
├── .env.example
├── bot/                 # Telegram: comandos + wizard + teclados
├── scraper/             # HTTP OLX + parser
├── database/            # modelos SQLAlchemy + CRUD
├── scheduler/           # tarefas periódicas
└── data/                # bot.db (gitignored)
```

---

## Variáveis `.env` (opcionais)

| Variável                         | Padrão                    |
| -------------------------------- | ------------------------- |
| `ALERT_CHECK_INTERVAL_MINUTES`   | 30                        |
| `WATCHLIST_CHECK_INTERVAL_HOURS` | 6                         |
| `DATABASE_URL`                   | SQLite em `./data/bot.db` |
| `SCRAPER_DELAY_MIN` / `MAX`      | 2–5 s entre requests      |

---

## Testes
O projeto tem testes unitários com `pytest` em `tests/`.

Para rodar:
```bash
py -m pip install pytest pytest-asyncio
pytest -q
```

Esses testes cobrem:
- `tests/test_crud.py`: CRUD no SQLite (async)
- `tests/test_parser.py`: parsing do `__NEXT_DATA__` e normalização de campos
- `tests/test_scraper_url.py`: montagem de URL de busca + extração do ID
- `tests/test_local_filters.py`: filtros pós-scraping (quartos, m² e bairros)

---
