#!/usr/bin/env bash
# Bootstrap único da infra de state:
#   1) cria o bucket S3 do state (fora do Terraform) com versioning
#   2) confere o GitHub OIDC provider (thumbprint muda — criado manualmente)
set -euo pipefail

REGION="${AWS_REGION:-sa-east-1}"
STATE_BUCKET="${STATE_BUCKET:-imovel-radar-tfstate}"

ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"

echo "==> Criando bucket de state: $STATE_BUCKET ($REGION)"
aws s3api create-bucket \
  --bucket "$STATE_BUCKET" \
  --region "$REGION" \
  --create-bucket-configuration LocationConstraint="$REGION" || echo ". (já existia?)"

echo "==> Versioning ON"
aws s3api put-bucket-versioning --bucket "$STATE_BUCKET" \
  --versioning-configuration Status=Enabled

echo "==> Bloqueio de acesso público"
aws s3api put-public-access-block --bucket "$STATE_BUCKET" \
  --public-access-block-configuration \
  BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true

echo "==> GitHub OIDC provider"
OIDC_ARN="arn:aws:iam::${ACCOUNT_ID}:oidc-provider/token.actions.githubusercontent.com"
if aws iam get-open-id-connect-provider --open-id-connect-provider-arn "$OIDC_ARN" >/dev/null 2>&1; then
  echo "OIDC provider já existe: $OIDC_ARN"
else
  echo "OIDC provider não existe. Crie manualmente (o thumbprint muda e precisa ser atualizado):"
  echo "  https://docs.github.com/en/actions/security-for-github-actions/security-hardening-your-deployments/"
  echo "  aws iam create-open-id-connect-provider \\"
  echo "    --url https://token.actions.githubusercontent.com --client-id-list sts.amazonaws.com \\"
  echo "    --thumbprint-list <THUMBPRINT_ATUAL>"
fi

echo
echo "Pronto. Agora rode:"
echo "  cd infra"
echo "  terraform init \\"
echo "    -backend-config=\"bucket=$STATE_BUCKET\" \\"
echo "    -backend-config=\"key=imovel-radar/terraform.tfstate\" \\"
echo "    -backend-config=\"region=$REGION\" \\"
echo "    -backend-config=\"use_lockfile=true\""
