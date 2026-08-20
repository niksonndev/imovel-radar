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
      "dynamodb:Scan",
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

# ── Bot Lambda function (webhook + notificação) ────────────────────────────
resource "aws_lambda_function" "bot" {
  function_name = "${var.project}-${var.environment}-bot-webhook"
  role          = aws_iam_role.bot_lambda.arn
  handler       = "lambda_handler.lambda_handler"
  runtime       = "python3.13"
  timeout       = var.bot_timeout
  memory_size   = var.bot_memory

  s3_bucket         = aws_s3_bucket.artifacts.id
  s3_key            = aws_s3_object.bot_artifact.id
  s3_object_version = aws_s3_object.bot_artifact.version_id

  environment {
    variables = {
      DATABASE_URL    = var.database_url
      DYNAMODB_TABLE  = aws_dynamodb_table.conversation_state.name
      SSM_TOKEN_PARAM = var.bot_ssm_token_name
      LOG_LEVEL       = "INFO"
    }
  }
}

# ── API Gateway (webhook do Telegram) ──────────────────────────────────────
resource "aws_apigatewayv2_api" "bot_webhook" {
  name          = "${var.project}-${var.environment}-bot-webhook-api"
  protocol_type = "HTTP"
}

resource "aws_apigatewayv2_integration" "bot_webhook" {
  api_id                 = aws_apigatewayv2_api.bot_webhook.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.bot.invoke_arn
  payload_format_version = "2.0"

  timeout_milliseconds = 29000
}

resource "aws_apigatewayv2_route" "bot_webhook_post" {
  api_id    = aws_apigatewayv2_api.bot_webhook.id
  route_key = "POST /webhook"
  target    = "integrations/${aws_apigatewayv2_integration.bot_webhook.id}"
}

resource "aws_apigatewayv2_stage" "bot_webhook" {
  api_id      = aws_apigatewayv2_api.bot_webhook.id
  name        = "$default"
  auto_deploy = true
}

resource "aws_lambda_permission" "bot_webhook_apigw" {
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.bot.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.bot_webhook.execution_arn}/$default"
}

# ── EventBridge — notificação horária (EventBridge → bot Lambda) ───────────
resource "aws_cloudwatch_event_rule" "bot_notify" {
  name                = "${var.project}-${var.environment}-bot-notify"
  schedule_expression = var.bot_notify_cron
}

resource "aws_cloudwatch_event_target" "bot_notify" {
  rule = aws_cloudwatch_event_rule.bot_notify.name
  arn  = aws_lambda_function.bot.arn
}

resource "aws_lambda_permission" "bot_notify" {
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.bot.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.bot_notify.arn
}

# ── Logs + alarme ──────────────────────────────────────────────────────────
resource "aws_cloudwatch_log_group" "bot" {
  name              = "/aws/lambda/${aws_lambda_function.bot.function_name}"
  retention_in_days = 14
}

resource "aws_cloudwatch_metric_alarm" "bot_errors" {
  alarm_name          = "${var.project}-${var.environment}-bot-webhook-errors"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "1"
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = "3600"
  statistic           = "Sum"
  threshold           = "0"
  alarm_description   = "Falha (Errors) na Bot Lambda (webhook/notificação)."
  dimensions = {
    FunctionName = aws_lambda_function.bot.function_name
  }
}