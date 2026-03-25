# Imóvel Radar — Bot Telegram (OLX Maceió)

![Demonstração: `/start`, menu principal e início do fluxo Novo Alerta](assets/demo-aluguel.gif)

Monitora anúncios de imóveis no [OLX](https://www.olx.com.br) em **Maceió/AL** e avisa no Telegram quando há **anúncios novos** que batem com seus filtros. Também permite **acompanhar um anúncio específico** (watchlist: mudança de preço ou remoção).

---

## Funcionalidades

- **Alertas por filtros** — Wizard guiado por botões (`/novo_alerta` ou **Novo Alerta** no menu): aluguel ou venda, faixa de preço (presets ou valores personalizados), bairros de Maceió (opcional), nome do alerta e confirmação. Após criar, o bot pode enviar um **carrossel** com amostra dos imóveis encontrados.
- **Notificações periódicas** — Jobs agendados consultam o OLX e enviam alertas só para anúncios **novos** em relação ao ciclo anterior (primeiro ciclo apenas “semeia” os IDs, sem spammar).
- **Menu inline no `/start`** — **Novo Alerta**, **Meus Alertas**, **Ajuda**, **Acompanhar Anúncio** (equivalente a enviar a URL, como em `/observar`).
- **Watchlist** — `/observar [url]` ou fluxo pelo menu; `/watchlist` e `/remover [id]` para gerir.
- **Gestão de alertas** — listar, pausar/reativar e apagar por id (`/meus_alertas`, `/pausar_alerta`, `/deletar_alerta`).
- **`/status`** — intervalos configurados e próximas execuções aproximadas do agendador.
- **`/start`** — Boas-vindas, menu principal e **reset** do estado da conversa (`user_data`), útil se o wizard ficar inconsistente.
- **`/cancelar`** — Cancela o wizard de novo alerta ou o fluxo de acompanhar anúncio.

O programa **não expõe servidor HTTP**: roda em **long polling** (`py main.py`) até você encerrar com **Ctrl+C**.

---

## O que o projeto faz (fluxo)

1. **`main.py`** — Ponto de entrada. Sobe o bot, registra comandos e, ao iniciar, abre o banco, o scraper e o agendador.
2. **`config.py`** — Lê `.env` (token e caminho do banco). Sem `TELEGRAM_BOT_TOKEN` o app nem sobe. O scheduler roda fixo 1x por dia.
3. **`bot/handlers.py`** — Comandos do Telegram (`/start`, `/observar`, …) e callbacks do menu (Meus Alertas, Ajuda).
4. **`bot/conversations.py`** — Wizard do `/novo_alerta` e fluxo curto “Acompanhar Anúncio”.
5. **`bot/carousel.py`** — Navegação inline após o seed imediato de anúncios.
6. **`scraper/`** — Baixa páginas do OLX, monta URL de busca Maceió, extrai lista de anúncios (HTML + JSON embutido).

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

O SQLite fica em **`data/bot.db`** (criado automaticamente).

---

## Lint com Ruff

Rodar o lint:

```bash
py -m ruff check .
```

Se quiser aplicar correções automáticas:

```bash
py -m ruff check . --fix
```

(O Ruff está configurado no `pyproject.toml` para focar em erros reais e imports, sem reclamar de `E501` por enquanto.)

---

## Comandos no Telegram

| Comando                | O que faz                                                       |
| ---------------------- | --------------------------------------------------------------- |
| `/start`               | Boas-vindas + menu inline; limpa estado da conversa do usuário  |
| `/novo_alerta`         | Criar alerta (aluguel/venda, preço, bairros, nome, confirmação) |
| `/meus_alertas`        | Listar alertas                                                  |
| `/pausar_alerta [id]`  | Pausar/reativar                                                 |
| `/deletar_alerta [id]` | Apagar alerta                                                   |
| `/observar [url]`      | Monitorar um anúncio (preço / sumiu)                            |
| `/watchlist`           | Ver observados                                                  |
| `/remover [id]`        | Tirar da watchlist                                              |
| `/status`              | Próximas verificações agendadas                                 |
| `/ajuda`               | Lista de comandos                                               |
| `/cancelar`            | Cancelar wizard de alerta ou fluxo de acompanhar anúncio        |

---

## Estrutura de pastas

```
imovel-radar/
├── main.py              # ← você roda isso
├── config.py            # .env + constantes
├── requirements.txt
├── .env.example
├── assets/              # mídias (ex.: demo no README)
├── bot/                 # Telegram: comandos + wizard + teclados + carrossel
├── scraper/             # HTTP OLX + parser
├── database/            # modelos + CRUD
├── scheduler/           # tarefas periódicas
└── data/                # bot.db (gitignored)
```

---

## Variáveis `.env` (opcionais)

| Variável                    | Padrão                    |
| --------------------------- | ------------------------- |
| `DATABASE_URL`              | SQLite em `./data/bot.db` |
| `SCRAPER_DELAY_MIN` / `MAX` | 2–5 s entre requests      |

---

## Verificação manual sem bot

Para rodar uma checagem manual de scraping + atualização de cache sem subir o Telegram:

```bash
py scripts/run_scrape_once.py
```
