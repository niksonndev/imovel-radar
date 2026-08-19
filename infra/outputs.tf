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
