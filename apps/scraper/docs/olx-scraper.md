# OLX Scraper

O scraper utiliza `cloudscraper` para bypassar proteções Cloudflare e extrai
anúncios do payload RSC (React Server Components) do App Router do OLX.

## Fluxo

1. **`search_all_rent_maceio()`** — função assíncrona principal
   - Itera páginas 1..N da listagem de aluguel em Maceió
   - Para cada página, chama `fetch(url)` que faz GET com delay aleatório (2-5s)
   - Extrai listings via `extract_listings_from_search_page(html)`
   - Deduplica por `listId`
   - Retorna `list[dict]` normalizado

2. **`fetch(url)`** — GET assíncrono com:
   - Delay aleatório entre requisições
   - User-Agent aleatório (roda entre 4 navegadores)
   - Headers simulando navegador real
   - Tratamento de `CloudflareChallengeError`

3. **`extract_listings_from_search_page(html)`** — Extração RSC:
   - Concatena chunks de `self.__next_f.push(...)` no HTML
   - Encontra arrays `"ads":[...]` via bracket-matching
   - Filtra candidatos com `listId`
   - Normaliza cada anúncio via `normalize_olx_listing()`

## Tratamento de erro

- `FetchError` — HTTP >= 400
- `ParseError` — falha ao extrair payload RSC
- `EmptyResultsError` — página HTTP 200 válida, porém sem resultados (fim normal da listagem)
- HTML é salvo em `debug_last_response.html` apenas quando **nenhum anúncio é extraído e a página não é reconhecida como fim de listagem** (falha real de parse)

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
- `SCRAPER_MAX_PAGES` (padrão 100) limita o número de páginas iteradas, evitando loops infinitos.
- Parada antecipada quando uma página não traz nenhum `listId` novo.

## Classes

| Classe | Descrição |
|--------|-----------|
| `FetchError` | HTTP status code error |
| `ParseError` | RSC parsing error |
| `EmptyResultsError` | Página vazia (fim da listagem) |