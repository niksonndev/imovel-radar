# OLX Scraper

O scraper usa `curl_cffi` com `impersonate="chrome150"` (fingerprint TLS/HTTP2
de Chrome 150) e extrai anúncios do payload RSC (React Server Components) do
App Router do OLX.

Próximo passo (ainda não implementado): GET da listagem com `RSC: 1` /
`Accept: text/x-component` (~268 KB em vez de ~1,02 MB de HTML). Checklist e
resultados do teste em [curl-cffi-rsc.md](curl-cffi-rsc.md).

## Fluxo

1. **`search_all_rent_maceio()`** — função assíncrona principal
   - Itera páginas 1..N da listagem de aluguel em Maceió
   - Para cada página, chama `fetch(url)` que faz GET com delay aleatório (2-5s)
   - Extrai listings via `extract_listings_from_search_page(html)`
   - Deduplica por `listId`
   - Retorna `list[dict]` normalizado

2. **`fetch(url)`** — GET assíncrono com:
   - Delay aleatório entre requisições
   - Fingerprint TLS/HTTP2 e headers de navegador vindos do `impersonate`
     (`Session(impersonate=IMPERSONATE, default_encoding="utf-8")`); o
     `_build_headers()` só acrescenta o `Referer` — nunca um User-Agent, que
     invalidaria o fingerprint
   - Retry de 403/429/502, de falha de rede (`RequestException` do curl_cffi,
     via `TransientFetchError`) e de corpo de challenge do Cloudflare devolvido
     em HTTP 200 (`_looks_like_challenge`)
   - Erro de rede persistente vira `FetchError(0, url)` após esgotar os retries

3. **`extract_listings_from_search_page(html)`** — Extração RSC:
   - Concatena chunks de `self.__next_f.push(...)` no HTML
   - Encontra arrays `"ads":[...]` via bracket-matching
   - Filtra candidatos com `listId`
   - Normaliza cada anúncio via `normalize_olx_listing()`

## Tratamento de erro

- `FetchError` — HTTP >= 400; também `FetchError(0, url)` quando os retries são
  esgotados (falha de rede ou challenge persistente)
- `TransientFetchError` — interna: falha retryável da camada HTTP
  (`RequestException` do curl_cffi). O `fetch` a converte em nova tentativa, com
  pausa maior e headers novos; não chega aos handlers
- `ParseError` — falha ao extrair payload RSC
- `EmptyResultsError` — página HTTP 200 válida, porém sem resultados (fim normal da listagem)
- HTML é salvo em `debug_last_response.html` apenas quando **nenhum anúncio é extraído e a página não é reconhecida como fim de listagem** (falha real de parse)

Bloqueio do Cloudflare: sem `cloudscraper` não há mais resolução de challenge JS.
O `fetch` detecta marcadores (`cf-chl`, `challenge-platform`, `Just a moment`,
`__cf_chl`) mesmo em HTTP 200 e trata como erro retryável, evitando que a página
de desafio seja interpretada como quebra de parse.

## Detecção da última página

O OLX, ao iterar além do fim da listagem, responde **HTTP 200** com uma página de
estado vazio (sem o array `"ads"` no payload RSC). Esse caso é reconhecido como
**fim normal da coleta** (não é erro) por `_is_empty_results_page()`:

1. Texto renderizado contém `OLX_EMPTY_RESULTS_TEXT` (padrão: `Nenhum anúncio foi encontrado`); ou
2. Fallback estrutural: um array `"ads":[]` presente, porém vazio.

Quando detectado, `search_all_rent_maceio()` encerra com log INFO, sem traceback e
sem gerar `debug_last_response.html`. Quebras reais de parse continuam lançando
`ParseError` (com traceback e dump de debug).

Salvaguardas adicionais:
- `SCRAPER_MAX_PAGES` (padrão 500) limita o número de páginas iteradas, evitando loops infinitos.
  Atingir o cap **não** marca a coleta como `completed` (não dispara
  `deactivate_missing_listings`) — só o fim real do OLX (página vazia / sem ads novos).
- Parada antecipada quando uma página não traz nenhum `listId` novo.

## Classes

| Classe | Descrição |
|--------|-----------|
| `FetchError` | HTTP status code error (`0` quando os retries esgotam) |
| `TransientFetchError` | Falha retryável (rede/challenge) — consumida pelo `fetch` |
| `ParseError` | RSC parsing error |
| `EmptyResultsError` | Página vazia (fim da listagem) |