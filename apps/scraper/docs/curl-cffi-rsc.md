# curl_cffi + RSC — notas da sessão (28 set 2026)

Proposta para o próximo ciclo: trocar `cloudscraper` por **curl_cffi** com
impersonate Chrome 150, pedir o payload RSC da listagem (`RSC: 1`) e
simplificar headers. Isto **ainda não está no código**. O teste foi local
(venv temporário), não da Lambda.

Não existe API pública de busca da OLX para substituir o GET da listagem.
A API oficial ([developers.olx.com.br](https://developers.olx.com.br/anuncio/api/home.html))
é OAuth de **anunciante** (publicar/editar o próprio inventário).

## Estado atual

- Cliente HTTP: `cloudscraper==1.2.71` em `collector/olx_scraper.py`,
  `scripts/extract_ad.py` e `scripts/extract_ad_venda.py`.
- GET da página pública (`www.olx.com.br/imoveis/...` com `sf`, `o`, `ps`, `pe`).
- Extração do JSON embutido no HTML (`self.__next_f.push` / App Router).
- `USER_AGENTS` em `config.py` (Chrome 120 / Firefox 121) + headers manuais
  (`Accept`, `Referer`, `Sec-Fetch-*`, etc.).
- `CloudflareChallengeError` tratado no fetch.

Isso já é scraping por request (sem browser). O dado útil já vem como JSON
dentro da página; não é parse de cards no DOM.

## Versões

| Pacote | No scraper hoje | Mais novo no teste | Para deploy |
|---|---|---|---|
| `cloudscraper` | 1.2.71 (abr 2023) | — | remover |
| `curl_cffi` | ausente | **0.16.4b1** (20 set 2026) | pin **0.16.3** (estável, 2 set 2026) |

- `requires-python` do curl_cffi: `>=3.10`. Wheel `cp310-abi3` manylinux x86_64
  (~14 MB no PyPI). Rodou no Python **3.13** do scraper.
- `impersonate="chrome"` resolveu para **chrome150** (`DEFAULT_CHROME`).
- Presets também ok no teste: `chrome136`, `safari`.

Não misturar UA aleatório (Firefox 121 / Chrome 120) com fingerprint Chrome 150.
Deixar o impersonate mandar o User-Agent.

## Teste HTTP (listagem aluguel Maceió)

URL: `https://www.olx.com.br/imoveis/aluguel/estado-al/alagoas/maceio`  
Parser: `extract_listings_from_search_page` (o mesmo do collector).  
Máquina local, Python 3.13.

| Caso | HTTP | Tempo | Ads | Challenge CF |
|---|---|---|---|---|
| cloudscraper + headers atuais | 200 | 808 ms | 50 | não |
| curl_cffi `chrome` (sem headers custom) | 200 | 623 ms | 50 | não |
| curl_cffi `chrome` + headers atuais | 200 | 1561 ms | 50 | não |
| curl_cffi `chrome150` | 200 | 284 ms | 50 | não |
| curl_cffi `chrome136` | 200 | 410 ms | 50 | não |
| curl_cffi `safari` | 200 | 643 ms | 50 | não |

HTML ~1.0 MB, título igual, payload RSC presente. Drop-in: `Session.get` +
`close()`. Não há `CloudflareChallengeError` — bloqueio vira HTTP 403/429 ou
`RequestsError`.

**Não testado:** IP da Lambda / datacenter (o ADR 0004 já relatou 403 com
cloudscraper em alguns ambientes). Impersonate TLS costuma ser melhor, mas
precisa de um GET real da Lambda antes de considerar a troca fechada.

## RSC `text/x-component` (mesmo URL)

```http
GET /imoveis/aluguel/estado-al/alagoas/maceio?sf=1
RSC: 1
Accept: text/x-component
```

| | HTML atual | `RSC: 1` |
|---|---|---|
| `Content-Type` | `text/html` | `text/x-component` |
| Tamanho | ~1.02 MB | **~268 KB** (~4× menor) |
| `"listId"` no body | precisa do parse dos `<script>` | **50** no stream |

Continua sendo o endpoint da **página**, contrato interno do Next.js, sujeito
a quebrar no próximo deploy. Ganho: menos bytes, parse potencialmente sem
BeautifulSoup no caminho quente da listagem.

`_is_empty_results_page()` hoje olha texto renderizado no HTML
(`OLX_EMPTY_RESULTS_TEXT`). Com RSC puro isso precisa de outro sinal
(`"ads":[]` no flight, ou um GET HTML só nesse caso).

Caminhos inventados (`/api/v2/ads`, `/graphql` em `www.olx.com.br`) devolvem
o SPA (HTML 200). `apigw.olx.com.br` existe no JS da listagem para conta,
favorito, lead e loja PRO — **não** para busca de mercado. Sondas
`/v1/listings` etc. → 404 `"no Route matched"`.

`search-microfrontends.olx.com.br` é CDN de remoteEntry (Module Federation),
não API de ads.

## Pacote Lambda

`curl_cffi` traz lib nativa. No venv de teste, `curl_cffi/_wrapper.abi3.so`
descompactado ~**38 MB** (o wheel manylinux ~14 MB). `cloudscraper` é puro
Python e leve.

Limites AWS (zip direto, sem container): 50 MB zipado / 250 MB descompactado.
O zip atual já inclui psycopg, lxml, etc. **Obrigatório** medir
`apps/scraper/dist/lambda.zip` depois do `uv pip install --target` do workflow
(`.github/workflows/infra-deploy.yml`, step *Build scraper Lambda zip*).

Amazon Linux / manylinux2014 x86_64: o wheel `cp310-abi3-manylinux_2_17`
deve servir a Lambda x86_64. Confirmar arquitetura do Terraform (não arm64
sem wheel correspondente).

## Superfície de código a readaptar

| Onde | O quê |
|---|---|
| `pyproject.toml` / `uv.lock` | `curl_cffi==0.16.3`; tirar `cloudscraper` |
| `collector/olx_scraper.py` | `Session(impersonate="chrome150")`; GET com `RSC: 1`; erros HTTP/`RequestsError`; `close()` |
| `config.py` | remover `USER_AGENTS` (e o `RuntimeError` se a lista ficar vazia) |
| `_build_headers()` | não forçar UA; no máximo `Accept: text/x-component` + `RSC: 1` |
| parse | stream RSC em vez de concatenar `__next_f.push` do HTML; empty-results e clamp (`<title>` Página N) |
| `scripts/extract_ad.py` | mesmo cliente |
| `scripts/extract_ad_venda.py` | mesmo cliente |
| `scripts/debug_scraper.py` | dump RSC / HTML de debug |
| testes | `test_olx_scraper.py` (empty page / parse error / `_sync_get`); fixtures HTML vs flight |
| `docs/olx-scraper.md`, `.clinerules/scraper.md` | atualizar cliente |

BeautifulSoup/lxml podem permanecer se o clamp e o empty-state ainda precisarem
do HTML; senão aí sim avaliar remover do caminho quente.

## Checklist de implementação

- [ ] Pin `curl_cffi==0.16.3` (não 0.16.4b1 em prod) e `uv lock`
- [ ] `requests.Session(impersonate="chrome150")` (ou `"chrome"`, que hoje alias chrome150)
- [ ] GET da listagem com `RSC: 1` e `Accept: text/x-component`
- [ ] Remover `USER_AGENTS` e headers que briguem com o fingerprint
- [ ] Mapear 403/429/502 e `RequestsError` no lugar de `CloudflareChallengeError`
- [ ] Readaptar extração: `listId` / `"ads"` no flight; empty-results sem `soup.get_text`
- [ ] Clamp de página (`o=101` → Página 100): hoje lê `<title>`; definir equivalente no RSC ou fallback HTML
- [ ] Scripts `extract_ad.py`, `extract_ad_venda.py`, `debug_scraper.py`
- [ ] Testes unitários + um GET de fumaça (Maceió aluguel, 50 ads)
- [ ] Medir zip da Lambda (`du -h dist/lambda.zip`; unzipped `du -sh dist/python`) e caber no limite
- [ ] GET de fumaça **a partir da Lambda** (ou invoke com URL real) — 200 + ads, sem challenge
- [ ] Atualizar `docs/olx-scraper.md` e `.clinerules/scraper.md` quando o código mudar
- [ ] Delay 2–4 s entre páginas permanece (não é ganho desta troca)

## O que isto não é

- Não é API estável da OLX. É o mesmo scrape, com cliente TLS melhor e payload
  menor.
- Terceiros tipo GeckoAPI só reempacotam scrape pago.
- 0.16.4b1 funcionou no teste; deploy fica em **0.16.3** até haver motivo para beta.
