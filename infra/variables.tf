variable "region" {
  description = "Região AWS de deploy"
  default     = "sa-east-1"
}

variable "project" {
  default = "imovel-radar"
}

variable "environment" {
  default = "prod"
}

variable "github_repo" {
  description = "Repo do GitHub no formato owner/repo (também usado no trust do OIDC)"
  default     = "niksonndev/imovel-radar"
}

# State bucket — criado no bootstrap, fora do Terraform.
variable "state_bucket" {
  default = "imovel-radar-tfstate"
}

variable "state_key" {
  default = "imovel-radar/terraform.tfstate"
}

variable "artifact_bucket" {
  default = "imovel-radar-lambda-artifacts"
}

variable "artifact_key" {
  default = "scraper/lambda.zip"
}

variable "zip_path" {
  description = "Caminho local do zip da Lambda (passado pelo CI; necessário p/ apply)"
  default     = ""
}

variable "database_url" {
  description = "Connection string do Postgres (Neon). Sensível."
  sensitive   = true
}

variable "scraper_max_pages" {
  description = "Limite de páginas do OLX por coleta (default hardcoded do config.py)"
  default     = 100
}

variable "scraper_cron" {
  description = "Cron do EventBridge em UTC — 08:00 America/Maceio = cron(0 11 * * ? *)"
  default     = "cron(0 11 * * ? *)"
}

variable "lambda_memory" {
  default = 512
}

variable "lambda_timeout" {
  description = "Timeout da Lambda (max 900s)"
  default     = 900
}

# ── Bot (webhook + notificação) ─────────────────────────────────────────────
variable "bot_ssm_token_name" {
  description = "Caminho do parâmetro SSM com o token do bot (criado no bootstrap, fora do Terraform)"
  default     = "/imovel-radar/prod/telegram_bot_token"
}

variable "conversation_ttl_hours" {
  description = "TTL (horas) dos drafts de conversa no DynamoDB (ADR 0006)"
  default     = 4
}

variable "bot_notify_cron" {
  description = "Cron do EventBridge para o job de notificação do bot (UTC) — 1x/hora"
  default     = "cron(0 * * * ? *)"
}

# Usadas a partir do corte 2 (função + trigger). Default vazio não quebra o plan.
variable "bot_zip_path" {
  description = "Caminho local do zip da Bot Lambda (passado pelo CI no corte 2)"
  default     = ""
}

variable "bot_memory" {
  description = "Memória da Bot Lambda (MB)"
  default     = 512
}

variable "bot_timeout" {
  description = "Timeout da Bot Lambda (s) — webhook precisa responder em ≤ 29s via API Gateway"
  default     = 60
}
