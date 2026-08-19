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
