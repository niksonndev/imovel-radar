#!/usr/bin/env bash
# Grava terraform output market_stats_url em NEXT_PUBLIC_MARKET_STATS_URL
# (produção) e dispara um deploy de produção só quando o valor mudou.
set -euo pipefail

KEY="NEXT_PUBLIC_MARKET_STATS_URL"

if [[ -z "${VERCEL_TOKEN:-}" || -z "${VERCEL_PROJECT_ID:-}" ]]; then
  echo "::error::Defina os secrets VERCEL_TOKEN e VERCEL_PROJECT_ID. Se o projeto estiver num time, defina também VERCEL_ORG_ID."
  exit 1
fi

URL="$(terraform -chdir=infra output -raw market_stats_url)"
if [[ -z "$URL" || "$URL" != https://* ]]; then
  echo "::error::market_stats_url inválida: ${URL:-vazia}"
  exit 1
fi
echo "market_stats_url=${URL}"

team_qs=""
if [[ -n "${VERCEL_ORG_ID:-}" ]]; then
  team_qs="?teamId=${VERCEL_ORG_ID}"
fi

api() {
  local method="$1"
  local path="$2"
  local out="$3"
  local body="${4:-}"
  local code
  if [[ -n "$body" ]]; then
    code="$(curl -sS -o "$out" -w '%{http_code}' -X "$method" \
      -H "Authorization: Bearer ${VERCEL_TOKEN}" \
      -H "Content-Type: application/json" \
      -d "$body" \
      "https://api.vercel.com${path}")"
  else
    code="$(curl -sS -o "$out" -w '%{http_code}' -X "$method" \
      -H "Authorization: Bearer ${VERCEL_TOKEN}" \
      "https://api.vercel.com${path}")"
  fi
  if [[ "$code" != "200" && "$code" != "201" ]]; then
    echo "::error::Vercel ${method} ${path%%\?*} respondeu HTTP ${code}. Se o projeto está num time, confira VERCEL_ORG_ID."
    cat "$out"
    echo
    exit 1
  fi
}

workdir="$(mktemp -d)"
trap 'rm -rf "$workdir"' EXIT

api GET "/v9/projects/${VERCEL_PROJECT_ID}/env${team_qs}" "$workdir/envs.json"

ENV_ID="$(jq -r --arg key "$KEY" '
  (if type == "array" then . else (.envs // []) end)
  | map(select(.key == $key))
  | map(select(
      .target == "production"
      or ((.target | type) == "array" and any(.target[]; . == "production"))
    ))
  | .[0].id // empty
' "$workdir/envs.json")"

if [[ -n "$ENV_ID" ]]; then
  api GET "/v1/projects/${VERCEL_PROJECT_ID}/env/${ENV_ID}${team_qs}" "$workdir/current.json"
  CURRENT="$(jq -r '.value // empty' "$workdir/current.json")"
  if [[ -n "$CURRENT" && "$CURRENT" == "$URL" ]]; then
    echo "${KEY} já aponta para o API Gateway; sem rebuild."
    exit 0
  fi

  payload="$(jq -n --arg url "$URL" '{
    value: $url,
    type: "plain",
    comment: "URL do API Gateway (terraform output market_stats_url). Gravada pelo workflow infra-deploy."
  }')"
  api PATCH "/v9/projects/${VERCEL_PROJECT_ID}/env/${ENV_ID}${team_qs}" "$workdir/write.json" "$payload"
else
  payload="$(jq -n --arg url "$URL" --arg key "$KEY" '{
    key: $key,
    value: $url,
    type: "plain",
    target: ["production"],
    comment: "URL do API Gateway (terraform output market_stats_url). Gravada pelo workflow infra-deploy."
  }')"
  api POST "/v10/projects/${VERCEL_PROJECT_ID}/env${team_qs}" "$workdir/write.json" "$payload"
  if jq -e '(.failed // []) | length > 0' "$workdir/write.json" >/dev/null; then
    echo "::error::Vercel recusou a env ${KEY}."
    cat "$workdir/write.json"
    echo
    exit 1
  fi
fi

api GET "/v9/projects/${VERCEL_PROJECT_ID}${team_qs}" "$workdir/project.json"
if [[ "$(jq -r '.link.type // empty' "$workdir/project.json")" != "github" ]]; then
  echo "::error::Projeto Vercel sem repositório GitHub ligado; a env foi gravada, mas o rebuild de produção não rodou."
  exit 1
fi
if ! jq -e '.link.repoId' "$workdir/project.json" >/dev/null; then
  echo "::error::Projeto Vercel sem link.repoId; a env foi gravada, mas o rebuild de produção não rodou."
  exit 1
fi

deploy_qs="$team_qs"
payload="$(jq -n --slurpfile project "$workdir/project.json" '{
  name: $project[0].name,
  project: $project[0].id,
  target: "production",
  gitSource: {
    type: "github",
    repoId: $project[0].link.repoId,
    ref: ($project[0].link.productionBranch // "main")
  }
}')"
api POST "/v13/deployments${deploy_qs}" "$workdir/deploy.json" "$payload"
echo "Deployment $(jq -r '.id' "$workdir/deploy.json") https://$(jq -r '.url' "$workdir/deploy.json")"
