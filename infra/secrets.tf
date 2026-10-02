# Secret do banco usado pela Lambda e pelo gate de migration do CI.
# ATENÇÃO: o valor aparece no state do Terraform (aceito p/ projeto pessoal).
resource "aws_ssm_parameter" "database_url" {
  name  = "/${var.project}/${var.environment}/database_url"
  type  = "SecureString"
  value = var.database_url
}
