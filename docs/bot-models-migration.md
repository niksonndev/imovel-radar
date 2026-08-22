# Migração: handlers consumindo `shared_models.tables` diretamente

> Refactor para eliminar a camada de conversão SQLModel → Pydantic em
> `apps/bot/handlers/api_client.py` (`to_shared_listing`, `to_shared_alert`,
> `UnnotifiedListItem`, `UnnotifiedListingsResult`), que existia só para
> manter o contrato da antiga API REST do scraper (ADR 0001), morta sob o
> acesso direto ao banco (ADR 0005).
>
> Estado intermediário consciente: entre pedaços, o `api_client` mistura
> tipos de retorno (`Alert` = table model, `Listing` ainda = Pydantic).

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

## ⬜ Pedaço 2 — Caminho `Listing`

- [ ] `carousel.py`: `properties` já é `dict` (sem `.model_dump()`);
      estado persistido em `bot_data`/DynamoDB com `model_dump(mode="json")`
      explícito (o dump da tabela inclui `first_seen_at`/`updated_at`
      como datetime)
- [ ] `api_client.get_unnotified_listings` → retorna
      `list[ListingAlertMatch]` direto (queries já devolvem isso)
- [ ] `polling_job.py` / `create_new_alert.py`: consumir `row.listing`
      e `row.alert_id`; carrossel recebe `[row.listing for row in rows]`
- [ ] Deletar `to_shared_listing`, `UnnotifiedListItem`,
      `UnnotifiedListingsResult` e os imports de `shared_models.models`

## ⬜ Pedaço 3 — Limpeza final

- [ ] Shims mortos no `api_client`: `create_user`, `get_user`
- [ ] Rename `handlers/api_client.py` (é camada de dados, não cliente
      HTTP) — item da Fase 2 da migration checklist

## Regras implícitas pós-migração

- Objetos table model são consumidos **fora** da `Session`: seguro porque
  só há colunas carregadas (sem relacionamentos/lazy-load), mas nada pode
  chamar `session.refresh()` depois.
- Carrosséis ativos salvos no formato antigo (dict do modelo Pydantic)
  expiram pelo TTL do DynamoDB (4 h) — "Carrossel expirado" é a UX.
