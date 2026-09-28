# OLX Scraper

O scraper usa `curl_cffi` com `impersonate="chrome150"` (fingerprint TLS/HTTP2 de
Chrome 150) e pede o **payload RSC** da listagem com `RSC: 1` /
`Accept: text/x-component`: a OLX responde o flight cru (~270 KB) em vez do HTML
renderizado (~1,0 MB), com os mesmos dados.

## Fluxo

1. **`search_all_rent_maceio()`** — função assíncrona principal
   - Itera páginas 1..N da listagem de aluguel em Maceió
   - Para cada página, chama `fetch(url)` que faz GET com delay aleatório (2-5s)
   - Extrai listings via `extract_listings_from_search_page(body)`
   - Deduplica por `listId`
   - Retorna `list[dict]` normalizado

2. **`fetch(url)`** — GET assíncrono com:
   - Delay aleatório entre requisições
   - Fingerprint TLS/HTTP2 e headers de navegador vindos do `impersonate`
     (`Session(impersonate=IMPERSONATE, default_encoding="utf-8")`); o
     `_build_headers()` só acrescenta `RSC_HEADERS` (`RSC: 1`,
     `Accept: text/x-component`) e o `Referer` — nunca um User-Agent, que
     invalidaria o fingerprint
   - Retry de 403/429/502, de falha de rede (`RequestException` do curl_cffi,
     via `TransientFetchError`) e de corpo de challenge do Cloudflare devolvido
     em HTTP 200 (`_looks_like_challenge`)
   - Erro de rede persistente vira `FetchError(0, url)` após esgotar os retries

3. **`extract_listings_from_search_page(body)`** — Extração RSC:
   - `_is_flight(body)` decide o caminho: flight cru (chunks prefixados pelo
     tamanho em hexa, ex. `1:"$Sreact.fragment"`) ou HTML (`<!DOCTYPE html>`,
     chunks de `self.__next_f.push(...)`)
   - Encontra arrays `"ads":[...]` via bracket-matching (há um `"ads":[]` de
     outro componente antes do array real; o maior candidato com `listId` vence)
   - Filtra candidatos com `listId`
   - Normaliza cada anúncio via `normalize_olx_listing()`

## Fixtures de flight

`tests/fixtures/olx_search_page_flight.txt.gz` (página com 50 anúncios) e
`olx_empty_page_flight.txt.gz` (fim da listagem) são respostas **reais**, só
comprimidas (~31 KB + ~13 KB contra 270 KB + 75 KB cruas). Para re-capturar:

```python
from curl_cffi.requests import Session

session = Session(impersonate="chrome150", default_encoding="utf-8")
r = session.get(url, timeout=90, headers={"RSC": "1", "Accept": "text/x-component"})
# url = .../alagoas/maceio?sf=1           → página com 50 anúncios
# url = .../alagoas/maceio?sf=1&o=100     → fim da listagem (fullPageTitle Página 100)
```


## Tratamento de erro

- `FetchError` — HTTP >= 400; também `FetchError(0, url)` quando os retries são
  esgotados (falha de rede ou challenge persistente)
- `TransientFetchError` — interna: falha retryável da camada HTTP
  (`RequestException` do curl_cffi). O `fetch` a converte em nova tentativa, com
  pausa maior e headers novos; não chega aos handlers
- `ParseError` — falha ao extrair payload RSC
- `EmptyResultsError` — página HTTP 200 válida, porém sem resultados (fim normal da listagem)
- A resposta crua (flight **ou** HTML) é salva em `debug_last_response.html`
  apenas quando **nenhum anúncio é extraído e a página não é reconhecida como
  fim de listagem** (falha real de parse). O log dessa falha traz
  `flight=True/False` e o `fullPageTitle`.

Bloqueio do Cloudflare: sem `cloudscraper` não há mais resolução de challenge JS.
O `fetch` detecta marcadores (`cf-chl`, `challenge-platform`, `Just a moment`,
`__cf_chl`) mesmo em HTTP 200 e trata como erro retryável, evitando que a página
de desafio seja interpretada como quebra de parse.

## Fim da listagem e clamp

Duas situações distintas, ambas com **HTTP 200**:

**Fim normal** — página sem anúncios, reconhecida por `_is_empty_results_page()`:

1. HTML: texto renderizado contém `OLX_EMPTY_RESULTS_TEXT` (padrão:
   `Nenhum anúncio foi encontrado`); ou
2. Estrutural (flight ou HTML): existe array `"ads":[]` e **todos** os arrays
   `"ads"` encontrados estão vazios. No flight é o único sinal disponível (o
   texto do estado vazio só existe no HTML renderizado).

Quando detectado, a coleta encerra com log INFO, sem traceback e sem gerar
`debug_last_response.html`. Quebras reais de parse continuam lançando
`ParseError` (com traceback e dump de debug).

**Clamp** — a OLX devolve uma página *anterior* à pedida (teto de paginação).
`o=101` volta como "Página 100" (mesmo corpo do `o=100`) e `is_clamped_page()`
marca `clamped=True`: a fatia encerra **sem** `completed`, para não disparar
`deactivate_missing_listings` sobre o que ficou de fora.

O número da página retornada vem de `returned_page_number()`:

| Resposta | Sinal |
|---|---|
| flight | `"fullPageTitle":"... - Página N \| OLX"` (regex) |
| HTML | `<title>` (o `fullPageTitle` dentro dos `<script>` vem escapado) |

Página 1 não informa número (retorna `None`).

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