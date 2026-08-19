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

## Bot infra — corte 1 (webhook/notificação)

Prepara a base da Bot Lambda sem criar a função (ela entra no corte 2, junto
com o código do bot). Recursos deste corte:

- **DynamoDB `imovel-radar-prod-conversation-state`** — estado de conversa do
  PTB (ADR 0006): PK `chat_id` (Number) + SK `store` (String), TTL nativo no
  atributo `ttl`, billing on-demand (free tier permanente). O atributo
  `version` é gravado pelo código (optimistic concurrency no `put_item`).
- **SSM `/imovel-radar/prod/telegram_bot_token`** — SecureString **fora do
  Terraform** (bootstrap), para o token nunca entrar no state.
- **IAM role `imovel-radar-prod-bot-webhook`** — execução da Bot Lambda:
  `AWSLambdaBasicExecutionRole` + leitura de secrets no SSM (token +
  `database_url`) + acesso à tabela de conversação.
- **Política de deploy do GitHub Actions ampliada** — permissões para criar a
  tabela DynamoDB, a role/policy do bot, ler o token e (no corte 2) a função
  Lambda, logs e alarmes.

### Bootstrap do token (uma vez)

```bash
aws ssm put-parameter --name /imovel-radar/prod/telegram_bot_token \
  --type SecureString --value 'SEU_TOKEN_DO_BOTFATHER'
```

O `./infra/bootstrap-state.sh` verifica a existência desse parâmetro de forma
idempotente.
