# Backend S3 com locking nativo (use_lockfile) — sem DynamoDB (deprecado).
# O bucket de state NÃO é gerenciado por este módulo (bootstrap único):
#   aws/infra/bootstrap-state.sh
terraform {
  backend "s3" {}
}
