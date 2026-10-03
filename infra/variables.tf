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

# ── Artefatos do scraper (zip único; evita re-deploy cruzado) ───────────────
variable "scraper_artifact_key" {
  default = "scraper/lambda.zip"
}

variable "scraper_zip_path" {
  description = "Caminho local do zip da Lambda de coleta (passado pelo CI; necessário p/ apply)"
  default     = "../apps/scraper/dist/lambda.zip"
}

variable "database_url" {
  description = "Connection string pooled do Neon (host com -pooler). Sensível."
  sensitive   = true
}

variable "scraper_max_pages" {
  description = "Limite de páginas do OLX por kind (default alinhado a config.py)"
  default     = 500
}

variable "scraper_cron" {
  description = "Cron do EventBridge em UTC — 08:00 America/Maceio = cron(0 11 * * ? *)"
  default     = "cron(0 11 * * ? *)"
}

variable "scraper_delta_cron" {
  description = "Cron do delta (recência) em UTC — de hora em hora por padrão"
  default     = "cron(0 * * * ? *)"
}

variable "lambda_memory" {
  default = 512
}

variable "lambda_timeout" {
  description = "Timeout da Lambda (max 900s)"
  default     = 900
}

variable "alarm_email" {
  description = "Email para notificações dos alarmes CloudWatch (SNS)"
  default     = "niksonndev@gmail.com"
}

variable "market_stats_cors_origins" {
  description = "Origens com CORS no GET /market-stats (domínio do site)"
  type        = list(string)
  default = [
    "https://imovel-radar.vercel.app",
    "https://imovel-radar-frontend.vercel.app",
  ]
}


