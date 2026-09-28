# curl_cffi + RSC — notas da sessão (28 set 2026)

**Status (28 set 2026):** o **Passo 1** — troca do cliente HTTP para curl_cffi
Chrome 150, mantendo o GET de HTML — **já está no código**. O **Passo 2** — GET
da listagem com `RSC: 1` / payload `text/x-component` — **ainda não está**. Os
números de HTTP deste documento vieram de venv temporário local (não da Lambda),
exceto onde anotado.

Não existe API pública de busca da OLX para substituir o GET da listagem.
A API oficial ([developers.olx.com.br](https://developers.olx.com.br/anuncio/api/home.html))
é OAuth de **anunciante** (publicar/editar o próprio inventário).

## Estado atual

- Cliente HTTP: **`curl_cffi==0.16.3`** com `impersonate="chrome150"`
  (`IMPERSONATE`) em `collector/olx_scraper.py`, `scripts/extract_ad.py` e
  `scripts/extract_ad_venda.py`. `cloudscraper` saiu do `pyproject.toml`/
  `uv.lock` (com ele: `requests`, `requests-toolbelt`, `pyparsing`, `urllib3`,
  `charset-normalizer`).
- GET da página pública (`www.olx.com.br/imoveis/...` com `sf`, `o`, `ps`, `pe`).
  **Ainda HTML** — os headers `RSC: 1` não entraram.
- Extração do JSON embutido no HTML (`self.__next_f.push` / App Router) —
  inalterada.
- `USER_AGENTS` **removido** de `config.py`; `_build_headers()` devolve só o
  `Referer` (UA, `Accept`, `Accept-Language`, `Sec-Fetch-*` vêm do impersonate).
- `CloudflareChallengeError` não existe mais: `RequestException` do curl_cffi
  vira `TransientFetchError` e entra no retry; challenge devolvido em HTTP 200 é
  detectado por `_looks_like_challenge` (cf-chl / challenge-platform /
  `Just a moment` / `__cf_chl`) e também é retryável.

Isso já é scraping por request (sem browser). O dado útil já vem como JSON
dentro da página; não é parse de cards no DOM.

## Versões

| Pacote | No scraper hoje | Mais novo no teste | Deploy |
|---|---|---|---|
| `cloudscraper` | — (removido no Passo 1) | — | removido |
| `curl_cffi` | **0.16.3** (pinado) | 0.16.4b1 (20 set 2026) | **0.16.3** — `chrome150` exige >= 0.16.1 |

- `requires-python` do curl_cffi: `>=3.10`. Wheel `cp310-abi3` manylinux x86_64
  (~14 MB no PyPI). Rodou no Python **3.13** do scraper.
- O alias `"chrome"` resolve para **chrome150** hoje, mas acompanha a versão do
  pacote — o código fixa `chrome150` explícito.
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

`curl_cffi` traz lib nativa. `curl_cffi/` descompactado no target: ~**38 MB**.
Medido localmente em 28 set 2026, reproduzindo o passo do CI
(`uv export --no-dev --frozen` + `uv pip install --target`):

| | Antes (cloudscraper) | Depois (curl_cffi 0.16.3) |
|---|---|---|
| zip (`lambda.zip`) | 25,7 MB | **38,8 MB** (37 MiB) |
| descompactado (`dist/python`) | — | **121,5 MB** (116 MiB) |

Limites AWS (zip direto, sem container): 50 MB zipado / 250 MB descompactado.
Cabe, mas a folga no zip caiu para ~11 MB. Não existe guard de tamanho no
workflow (`.github/workflows/infra-deploy.yml`, step *Build scraper Lambda zip*)
— vale adicionar um `stat -c%s` comparando com 50 MB.

Arquitetura resolvida: `infra/scraper-lambda.tf` não define `architectures`
(default **x86_64**) e roda `python3.13`; o wheel
`cp310-abi3-manylinux_2_17_x86_64` é o alvo correto (Amazon Linux também casa,
glibc 2.34 >= 2.17).

## Superfície de código a readaptar

| Onde | O quê | Status |
|---|---|---|
| `pyproject.toml` / `uv.lock` | `curl_cffi==0.16.3`; tirar `cloudscraper` | ✅ Passo 1 |
| `collector/olx_scraper.py` | `Session(impersonate="chrome150")`; `RequestException`/`TransientFetchError`; `close()` | ✅ Passo 1 |
| `collector/olx_scraper.py` | GET com `RSC: 1` + `Accept: text/x-component` | ⏳ Passo 2 |
| `config.py` | remover `USER_AGENTS` (e o `RuntimeError` se a lista ficar vazia) | ✅ Passo 1 |
| `_build_headers()` | não forçar UA (hoje: só `Referer`) | ✅ Passo 1 |
| parse | stream RSC em vez de concatenar `__next_f.push` do HTML; empty-results e clamp (`<title>` Página N) | ⏳ Passo 2 |
| `scripts/extract_ad.py` / `extract_ad_venda.py` | mesmo cliente | ✅ Passo 1 |
| `scripts/debug_scraper.py` | dump RSC / HTML de debug | ⏳ Passo 2 (usa `fetch()` do collector) |
| testes | `test_olx_scraper.py`: retry de rede, challenge em HTTP 200, headers sem UA, 404 sem retry | ✅ Passo 1 |
| testes | fixtures HTML vs flight | ⏳ Passo 2 |
| `docs/olx-scraper.md`, `.clinerules/scraper.md` | atualizar cliente | ✅ Passo 1 |

BeautifulSoup/lxml podem permanecer se o clamp e o empty-state ainda precisarem
do HTML; senão aí sim avaliar remover do caminho quente.

## Checklist de implementação

- [x] Pin `curl_cffi==0.16.3` (não 0.16.4b1 em prod) e `uv lock`
- [x] Sessão com `impersonate="chrome150"` (preset fixo; não o alias `"chrome"`)
- GET da listagem com `RSC: 1` e `Accept: text/x-component` — ⏳ **Passo 2**
- [x] Remover `USER_AGENTS` e headers que briguem com o fingerprint
- [x] Mapear 403/429/502 e `RequestException` no lugar de `CloudflareChallengeError`,
      mais `_looks_like_challenge` para o challenge devolvido em HTTP 200
- Readaptar extração (`listId` / `"ads"` no flight; empty-results sem `soup.get_text`) — ⏳ **Passo 2**
- Clamp de página (`o=101` → Página 100): hoje lê `<title>`; definir equivalente no RSC ou fallback HTML — ⏳ **Passo 2**
- Scripts `extract_ad.py` e `extract_ad_venda.py`: cliente trocado ✅ — `debug_scraper.py`: dump RSC ⏳ **Passo 2** (usa `fetch()` do collector, não precisou mudar)
- [x] Testes unitários (retry de rede, challenge em HTTP 200, headers sem UA manual,
      404 sem retry) + GET de fumaça local em 28 set 2026: **HTTP 200, 1.019.289
      bytes, 50 ads** (Maceió aluguel)
- [x] Medir zip da Lambda: **38,8 MB zipado / 121,5 MB descompactado** (limites 50 MB / 250 MB)
- [ ] GET de fumaça **a partir da Lambda** (ou invoke com URL real) — 200 + ads, sem challenge
      ⚠️ **é o gate do Passo 1**: nada aqui foi medido com IP de datacenter/Lambda
- [x] Atualizar `docs/olx-scraper.md`, `.clinerules/scraper.md` e este doc
- [x] Delay 2–4 s entre páginas permanece (não é ganho desta troca)

## O que isto não é

- Não é API estável da OLX. É o mesmo scrape, com cliente TLS melhor e payload
  menor.
- Terceiros tipo GeckoAPI só reempacotam scrape pago.
- 0.16.4b1 funcionou no teste; deploy fica em **0.16.3** até haver motivo para beta.
