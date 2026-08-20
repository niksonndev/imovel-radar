output "lambda_function_name" {
  value = aws_lambda_function.collect.function_name
}

output "lambda_arn" {
  value = aws_lambda_function.collect.arn
}

output "eventbridge_rule_arn" {
  value = aws_cloudwatch_event_rule.collect_schedule.arn
}

output "artifact_bucket" {
  value = aws_s3_bucket.artifacts.id
}

output "ssm_database_url_name" {
  value = aws_ssm_parameter.database_url.name
}

output "github_actions_role_arn" {
  value = aws_iam_role.github_actions.arn
}

# ── Bot (corte 1) ─────────────────────────────────────────────────────────────
output "conversation_table_name" {
  value = aws_dynamodb_table.conversation_state.name
}

output "bot_lambda_role_arn" {
  value = aws_iam_role.bot_lambda.arn
}

output "telegram_bot_token_ssm_name" {
  value = var.bot_ssm_token_name
}

output "bot_webhook_url" {
  description = "URL pública do webhook do Telegram (chamar setWebhook com este base)"
  value       = "${aws_apigatewayv2_api.bot_webhook.api_endpoint}/webhook"
}
