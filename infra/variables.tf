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
