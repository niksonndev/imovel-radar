# Migração: handlers consumindo `shared_models.tables` diretamente

> Refactor para eliminar a camada de conversão SQLModel → Pydantic em
> `apps/bot/handlers/api_client.py` (`to_shared_listing`, `to_shared_alert`,
> `UnnotifiedListItem`, `UnnotifiedListingsResult`), que existia só para
> manter o contrato da antiga API REST do scraper (ADR 0001), morta sob o
> acesso direto ao banco (ADR 0005).

## ✅ Pedaço 1 — Caminho `Alert` (feito)

- [x] `api_client`: removido `to_shared_alert`; `get_alerts_for_user`,
      `get_active_alerts_for_user` e `get_alert_for_user` retornam
      `shared_models.tables.Alert` direto
- [x] `ui/keyboards.py`: import de `tables`; guarda `a.id is not None`
      no teclado de pick (id é opcional antes do flush)
- [x] `ui/menus.py`: import de `tables`; `neighbourhoods` sem branch
      `json.loads` (resquício SQLite); `_meus_alertas_created_display`
      recebe `datetime | None` direto
- [x] `meus_alertas.py`: docstrings/logs desatualizados corrigidos

## ✅ Pedaço 2 — Caminho `Listing` (feito)

- [x] `api_client.get_unnotified_listings` → retorna
      `list[ListingAlertMatch]` direto (queries já devolviam isso);
      deletados `to_shared_listing`, `UnnotifiedListItem`,
      `UnnotifiedListingsResult` e os imports de `shared_models.models`
- [x] `carousel.py`: import de `tables.Listing`; `properties` usado como
      dict direto; estado em `bot_data` persistido com
      `model_dump(mode="json")` explícito (`first_seen_at`/`updated_at`
      viram strings ISO seguras p/ o JSON do DynamoDB)
- [x] `polling_job.py`: consome `row.listing`/`row.alert_id`;
      carrossel recebe `[row.listing for row in rows]`
- [x] `create_new_alert.py`: filtro por alerta sobre `ListingAlertMatch`

## ✅ Validação dos pedaços 1–2

- Smoke de imports de todos os módulos tocados
- Runtime check do carousel com table model: `_carousel_caption` renderiza
  a partir de dict e o roundtrip `model_dump(mode="json")` →
  `Listing(**…)` → caption é estável
- `ruff check .` + `pyright` limpos

## ✅ Pedaço 3 — Limpeza final

- [x] Shims mortos no `api_client`: `create_user`, `get_user` removidos
- [x] Rename `handlers/api_client.py` → `handlers/data.py`

## Regras implícitas pós-migração

- Objetos table model são consumidos **fora** da `Session`: seguro porque
  só há colunas carregadas (sem relacionamentos/lazy-load), mas nada pode
  chamar `session.refresh()` depois.
- Carrosséis ativos salvos no formato antigo (dict do modelo Pydantic)
  expiram pelo TTL do DynamoDB (4 h) — "Carrossel expirado" é a UX.
