# Infra — scraper Lambda (Terraform)

Provisiona a Lambda de coleta do OLX (trigger EventBridge) na região
`sa-east-1`, com custo $0 (free tiers de Lambda, EventBridge, S3, CloudWatch e
SSM Parameter Store).

## Recursos

- **S3 `imovel-radar-lambda-artifacts`** — zip da Lambda (versioning).
- **SSM `/imovel-radar/prod/database_url`** — connection string do Neon
  (SecureString).
- **IAM**: role de execução da Lambda (Logs + SSM) e role de deploy do GitHub
  Actions via OIDC.
- **Lambda `imovel-radar-prod-scraper-collect`** — python3.13, 512MB, timeout
  900s, env `DATABASE_URL` (do SSM), `SCRAPER_MAX_PAGES`.
- **EventBridge `imovel-radar-prod-scraper-collect-cron`** — `cron(0 11 * * ? *)`
  (08:00 America/Maceio em UTC).
- **CloudWatch**: log group (retention 14d) + alarme de erros da Lambda.

## Bootstrap (uma vez)

```bash
# 1) bucket de state + OIDC provider
./infra/bootstrap-state.sh

# 2) primeiro apply com credenciais administrativas locais
cd infra
terraform init \
  -backend-config="bucket=imovel-radar-tfstate" \
  -backend-config="key=imovel-radar/terraform.tfstate" \
  -backend-config="region=sa-east-1" \
  -backend-config="use_lockfile=true"
aws ssm put-parameter --name /imovel-radar/prod/database_url --type SecureString --value "postgresql+psycopg://..." --overwrite
terraform plan -var "zip_path=../apps/scraper/dist/lambda.zip" \
  -var 'database_url=postgresql+psycopg://...'
terraform apply -auto-approve -var "zip_path=..." -var 'database_url=...'

# 3) grave o ARN da role OIDC como secret do repo
terraform output github_actions_role_arn
```

O `terraform output github_actions_role_arn` vira o secret do GitHub
`AWS_ROLE_ARN` (usado pelo workflow infra-deploy.yml).

### OIDC provider note

O provider `token.actions.githubusercontent.com` precisa existir na conta;
ou thumbprint de GitHub é rotacionado — crie seguindo a doc oficial do GitHub.

## Deploy automático

`.github/workflows/infra-deploy.yml`: testes → migrations (gate bloqueante) →
build do zip → `terraform plan`/`apply` → smoke pós-deploy (10 páginas).

> ATENÇÃO: `database_url` aparece no state (projeto pessoal); o CI o passa por
> `-var`, então não fica hardcoded nos arquivos.

## Bot infra (webhook + notificação)

**Corte 1** (aplicado): DynamoDB de estado de conversa (ADR 0006), SSM do token,
IAM role `imovel-radar-prod-bot-webhook` e expansão da política de deploy.

**Corte 2** (este): cria a função Lambda do bot, API Gateway, EventBridge e
smoke/setWebhook no CI.

Recursos (o `terraform apply` cria/provisiona):

- **DynamoDB `imovel-radar-prod-conversation-state`** — estado de conversa do
  PTB (ADR 0006): PK `chat_id` (Number) + SK `store` (String), TTL nativo no
  atributo `ttl`, billing on-demand (free tier permanente). O atributo
  `version` é gravado pelo código (optimistic concurrency no `put_item`).
- **SSM `/imovel-radar/prod/telegram_bot_token`** — SecureString **fora do
  Terraform** (bootstrap), para o token nunca entrar no state.
- **IAM role `imovel-radar-prod-bot-webhook`** — execução da Bot Lambda:
  `AWSLambdaBasicExecutionRole` + leitura de secrets no SSM (token +
  `database_url`) + acesso à tabela de conversação (incl. `Scan`).
- **Bot Lambda `imovel-radar-prod-bot-webhook`** — python3.13, handler
  `lambda_handler.lambda_handler`, env `DATABASE_URL`, `DYNAMODB_TABLE`,
  `SSM_TOKEN_PARAM`, `LOG_LEVEL`. Distingue entre webhook e notificação pela
  origem do evento.
- **API Gateway** `imovel-radar-prod-bot-webhook-api` — HTTP API com rota
  `POST /webhook`, integração AWS_PROXY (timeout 29 s). URL no output.
- **EventBridge** `imovel-radar-prod-bot-notify` — cron horário → Lambda.
- **Logs + alarme CloudWatch** do webhook/notificação.

### Zip separados (scraper vs bot)

- `scraper_zip_path` → `dist/lambda.zip` do scraper (chave `scraper/lambda.zip`).
- `bot_zip_path` → `dist/lambda.zip` do bot (chave `bot/lambda.zip`).

Separar zips evita re-deploy cruzado (o acoplamento de `zip_path` reportado no
corte 1).

### Set webhook

`.github/workflows/infra-deploy.yml` chama `setWebhook` após o apply apontando
para `bot_webhook_url` (lido do output do terraform).

### Bootstrap do token (uma vez)

```bash
aws ssm put-parameter --name /imovel-radar/prod/telegram_bot_token \
  --type SecureString --value 'SEU_TOKEN_DO_BOTFATHER'
```

O `./infra/bootstrap-state.sh` verifica a existência desse parâmetro de forma
idempotente.
