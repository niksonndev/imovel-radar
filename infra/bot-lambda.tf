# ── Role de execução da Bot Lambda (webhook + notificação) ─────────────────
# Corte 1: role + permissões (SSM de secrets, DynamoDB do estado de conversa).
# A `aws_lambda_function` em si entra no corte 2 junto com o código do bot
# (handler webhook/notify) — não dá para criar a função sem o artefato zip.

data "aws_iam_policy_document" "bot_lambda_assume_role" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "bot_lambda" {
  name               = "${var.project}-${var.environment}-bot-webhook"
  assume_role_policy = data.aws_iam_policy_document.bot_lambda_assume_role.json
}

resource "aws_iam_role_policy_attachment" "bot_lambda_basic" {
  role       = aws_iam_role.bot_lambda.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# A role lê o token do bot e o DATABASE_URL do SSM e acessa o estado de
# conversa (DynamoDB, ADR 0006). Os ARNs do token são literais (padrão do
# oidc.tf) — o parâmetro é criado no bootstrap, fora do Terraform.
data "aws_iam_policy_document" "bot_lambda_secrets_and_state" {
  statement {
    sid     = "SsmReadSecrets"
    actions = ["ssm:GetParameter"]
    resources = [
      "arn:aws:ssm:${var.region}:*:parameter/${var.project}/${var.environment}/telegram_bot_token",
      aws_ssm_parameter.database_url.arn,
    ]
  }

  statement {
    sid = "DynamoDbConversationState"
    actions = [
      "dynamodb:GetItem",
      "dynamodb:PutItem",
      "dynamodb:UpdateItem",
      "dynamodb:DeleteItem",
      "dynamodb:Query",
    ]
    resources = [aws_dynamodb_table.conversation_state.arn]
  }
}

resource "aws_iam_policy" "bot_lambda_secrets_and_state" {
  name        = "${var.project}-${var.environment}-bot-webhook-secrets-state"
  description = "Permite a Bot Lambda ler secrets (SSM) e persistir estado de conversa (DynamoDB)"
  policy      = data.aws_iam_policy_document.bot_lambda_secrets_and_state.json
}

resource "aws_iam_role_policy_attachment" "bot_lambda_secrets_and_state" {
  role       = aws_iam_role.bot_lambda.name
  policy_arn = aws_iam_policy.bot_lambda_secrets_and_state.arn
}