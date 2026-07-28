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
- HTML é salvo em `debug_last_response.html` quando nenhum anúncio é extraído

## Classes

| Classe | Descrição |
|--------|-----------|
| `FetchError` | HTTP status code error |
| `ParseError` | RSC parsing error |