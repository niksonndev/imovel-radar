# curl_cffi + RSC — notas da sessão (28 set 2026)

**Status (28 set 2026):** **Passo 1** (cliente curl_cffi Chrome 150) e **Passo 2**
(GET com `RSC: 1` / payload `text/x-component`) **estão no código**. Falta só o
GET de fumaça a partir da Lambda (IP de datacenter), que é o gate de ambos. Os
números de HTTP deste documento vieram de máquina local (não da Lambda), exceto
onde anotado.

Não existe API pública de busca da OLX para substituir o GET da listagem.
A API oficial ([developers.olx.com.br](https://developers.olx.com.br/anuncio/api/home.html))
é OAuth de **anunciante** (publicar/editar o próprio inventário).

## Estado atual

- Cliente HTTP: **`curl_cffi==0.16.3`** com `impersonate="chrome150"`
  (`IMPERSONATE`) em `collector/olx_scraper.py`, `scripts/extract_ad.py` e
  `scripts/extract_ad_venda.py`. `cloudscraper` saiu do `pyproject.toml`/
  `uv.lock` (com ele: `requests`, `requests-toolbelt`, `pyparsing`, `urllib3`,
  `charset-normalizer`).
- GET da página pública (`www.olx.com.br/imoveis/...` com `sf`, `o`, `ps`, `pe`)
  pedindo **`RSC_HEADERS`** (`RSC: 1`, `Accept: text/x-component`): a resposta é o
  flight cru (~270 KB); o caminho HTML (~1,0 MB) continua suportado e é escolhido
  por `_is_flight()` (prefixo de chunk em hexa vs `<!DOCTYPE html>`).
- Extração: o flight é o payload inteiro (`_extract_rsc_payload` devolve o corpo);
  no HTML continua concatenando `self.__next_f.push`. O bracket-matching de
  `"ads":[...]` não mudou.
- Empty-state e clamp vieram do flight, sem GET HTML extra: `"ads":[]` em todos os
  candidatos = fim da listagem; `fullPageTitle` ("... Página N | OLX") é o
  equivalente do `<title>` para o clamp.
- `USER_AGENTS` **removido** de `config.py`; `_build_headers()` devolve
  `RSC_HEADERS` + `Referer` (UA, `Accept-Language`, `Sec-Fetch-*` vêm do
  impersonate).
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

| | HTML | `RSC: 1` (medido em 28 set 2026) |
|---|---|---|
| `Content-Type` | `text/html` | `text/x-component` |
| Tamanho | 1.019.289 bytes | **269.431 bytes** (3,8× menor) |
| `listId` no body | precisa do parse dos `<script>` | **50** no stream |
| Fim da listagem | texto renderizado | `"ads":[]` em todos os candidatos |
| Nº da página (clamp) | `<title>... Página N` | `"fullPageTitle":"... Página N \| OLX"` |

Continua sendo o endpoint da **página**, contrato interno do Next.js, sujeito a
quebrar no próximo deploy.

Duas armadilhas do flight, ambas cobertas por teste com payload real:

1. A página traz um **`"ads":[]` de outro componente** (`topoVipSelection`) antes
   do array real — por isso o candidato escolhido é o maior que tem `listId`
   (array real: 57 itens, 50 com `listId`).
2. `o=100` e `o=101` devolvem **o mesmo corpo** (74.995 bytes) com
   `fullPageTitle` "Página 100". O clamp sai de comparar a página pedida com a
   devolvida — igual ao que o `<title>` fazia.

Também medido: `o=2` devolveu **HTTP 502** (página de erro HTML, 6,4 KB) numa das
tentativas e 200 (246.538 bytes) na seguinte — ou seja, o retry de 502 continua
necessário, e uma resposta HTML não-flight passa pelo caminho HTML do parser.

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
| `collector/olx_scraper.py` | GET com `RSC: 1` + `Accept: text/x-component` (`RSC_HEADERS`) | ✅ Passo 2 |
| `config.py` | remover `USER_AGENTS` (e o `RuntimeError` se a lista ficar vazia) | ✅ Passo 1 |
| `_build_headers()` | não forçar UA (hoje: só `Referer`) | ✅ Passo 1 |
| parse | `_is_flight()` separa flight/HTML; empty-results estrutural (`"ads":[]`) e clamp via `fullPageTitle` | ✅ Passo 2 |
| `scripts/extract_ad.py` / `extract_ad_venda.py` | mesmo cliente | ✅ Passo 1 |
| `scripts/debug_scraper.py` | dump RSC / HTML de debug | ✅ não precisou mudar (usa `fetch()` e `_extract_rsc_payload`, que já aceitam flight) |
| testes | `test_olx_scraper.py`: retry de rede, challenge em HTTP 200, headers sem UA, 404 sem retry | ✅ Passo 1 |
| testes | fixtures HTML vs flight | ✅ Passo 2 (payload real, gzipado) |
| `docs/olx-scraper.md`, `.clinerules/scraper.md` | atualizar cliente | ✅ Passo 1+2 |

BeautifulSoup/lxml **permanecem**: o caminho HTML continua suportado (a OLX pode
devolver HTML, e uma página de erro/challenge é HTML), o texto do empty-state só
existe no HTML e o dump de debug é o corpo cru. No flight o BeautifulSoup não
entra no caminho quente (é `_is_flight` → devolve o corpo).

## Checklist de implementação

- [x] Pin `curl_cffi==0.16.3` (não 0.16.4b1 em prod) e `uv lock`
- [x] Sessão com `impersonate="chrome150"` (preset fixo; não o alias `"chrome"`)
- [x] GET da listagem com `RSC: 1` e `Accept: text/x-component` (`RSC_HEADERS`)
- [x] Remover `USER_AGENTS` e headers que briguem com o fingerprint
- [x] Mapear 403/429/502 e `RequestException` no lugar de `CloudflareChallengeError`,
      mais `_looks_like_challenge` para o challenge devolvido em HTTP 200
- [x] Readaptar extração: flight cru passa direto (`_extract_rsc_payload`) e o
      empty-state no flight usa o sinal estrutural (`"ads":[]` em todos os candidatos)
- [x] Clamp de página (`o=101` → Página 100): flight usa `fullPageTitle`; HTML
      mantém o `<title>` (nenhum GET HTML extra foi necessário)
- [x] Scripts `extract_ad.py`, `extract_ad_venda.py` e `debug_scraper.py`
      (o último não precisou mudar: usa `fetch()`/`_extract_rsc_payload`, que já
      aceitam flight)
- [x] Testes unitários (retry de rede, challenge em HTTP 200, headers sem UA manual,
      404 sem retry, + 8 do flight sobre payload real) + GETs de fumaça locais em
      28 set 2026: HTML **200 / 1.019.289 bytes / 50 ads**; flight **200 /
      269.431 bytes / 50 ads** (Maceió aluguel) e **302.295 bytes / 50 ads** numa
      fatia de venda Recife (500–550k)
- [x] Fixtures reais versionadas gzipadas (`olx_search_page_flight.txt.gz`,
      `olx_empty_page_flight.txt.gz`)
- [x] Caminho HTML preservado e testado (fixture `empty_results_page.html` +
      clamp por `<title>`)
- [x] Medir zip da Lambda: **38,8 MB zipado / 121,5 MB descompactado** (limites 50 MB / 250 MB)
- [ ] GET de fumaça **a partir da Lambda** (ou invoke com URL real) — 200 + ads, sem challenge
      ⚠️ **é o gate dos Passos 1 e 2**: nada aqui foi medido com IP de datacenter/Lambda
- [x] Atualizar `docs/olx-scraper.md`, `.clinerules/scraper.md` e este doc
- [x] Delay 2–4 s entre páginas permanece (não é ganho desta troca)

## O que isto não é

- Não é API estável da OLX. É o mesmo scrape, com cliente TLS melhor e payload
  menor.
- Terceiros tipo GeckoAPI só reempacotam scrape pago.
- 0.16.4b1 funcionou no teste; deploy fica em **0.16.3** até haver motivo para beta.
