# ── Role de execução da Lambda ──────────────────────────────────────────────
data "aws_iam_policy_document" "lambda_assume_role" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "scraper_lambda" {
  name               = "${var.project}-${var.environment}-scraper-collect"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume_role.json
}

resource "aws_iam_role_policy_attachment" "scraper_lambda_basic" {
  role       = aws_iam_role.scraper_lambda.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

data "aws_iam_policy_document" "scraper_lambda_ssm" {
  statement {
    actions   = ["ssm:GetParameter"]
    resources = [aws_ssm_parameter.database_url.arn]
  }
}

data "aws_caller_identity" "current" {}

data "aws_iam_policy_document" "scraper_lambda_self_invoke" {
  statement {
    actions = ["lambda:InvokeFunction"]
    # ARN por nome evita ciclo Terraform (policy ↔ function).
    resources = [
      "arn:aws:lambda:${var.region}:${data.aws_caller_identity.current.account_id}:function:${var.project}-${var.environment}-scraper-collect"
    ]
  }
}

resource "aws_iam_policy" "scraper_lambda_ssm" {
  name        = "${var.project}-${var.environment}-scraper-collect-ssm"
  description = "Permite a Lambda ler o connection string do banco (SSM)"
  policy      = data.aws_iam_policy_document.scraper_lambda_ssm.json
}

resource "aws_iam_policy" "scraper_lambda_self_invoke" {
  name        = "${var.project}-${var.environment}-scraper-collect-self-invoke"
  description = "Permite a Lambda auto-invocar para continuar chunks de coleta"
  policy      = data.aws_iam_policy_document.scraper_lambda_self_invoke.json
}

resource "aws_iam_role_policy_attachment" "scraper_lambda_ssm" {
  role       = aws_iam_role.scraper_lambda.name
  policy_arn = aws_iam_policy.scraper_lambda_ssm.arn
}

resource "aws_iam_role_policy_attachment" "scraper_lambda_self_invoke" {
  role       = aws_iam_role.scraper_lambda.name
  policy_arn = aws_iam_policy.scraper_lambda_self_invoke.arn
}

# ── Lambda function ────────────────────────────────────────────────────────
resource "aws_lambda_function" "collect" {
  function_name = "${var.project}-${var.environment}-scraper-collect"
  role          = aws_iam_role.scraper_lambda.arn
  handler       = "lambda_handler.lambda_handler"
  runtime       = "python3.13"
  timeout       = var.lambda_timeout
  memory_size   = var.lambda_memory

  s3_bucket         = aws_s3_bucket.artifacts.id
  s3_key            = aws_s3_object.scraper_artifact.id
  s3_object_version = aws_s3_object.scraper_artifact.version_id

  environment {
    variables = {
      DATABASE_URL      = var.database_url
      LOG_LEVEL         = "INFO"
      SCRAPER_MAX_PAGES = tostring(var.scraper_max_pages)
    }
  }
}

# ── EventBridge (cron) ─────────────────────────────────────────────────────
resource "aws_cloudwatch_event_rule" "collect_schedule" {
  name                = "${var.project}-${var.environment}-scraper-collect-cron"
  schedule_expression = var.scraper_cron
}

resource "aws_cloudwatch_event_target" "collect_schedule" {
  rule = aws_cloudwatch_event_rule.collect_schedule.name
  arn  = aws_lambda_function.collect.arn
  input = jsonencode({
    listing_kind = "aluguel"
    start_page   = 1
  })
}

resource "aws_lambda_permission" "collect_schedule" {
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.collect.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.collect_schedule.arn
}

# ── Logs + alarme ──────────────────────────────────────────────────────────
resource "aws_cloudwatch_log_group" "collect" {
  name              = "/aws/lambda/${aws_lambda_function.collect.function_name}"
  retention_in_days = 14
}

resource "aws_sns_topic" "alarms" {
  name = "${var.project}-${var.environment}-alarms"
}

resource "aws_sns_topic_subscription" "alarms_email" {
  topic_arn = aws_sns_topic.alarms.arn
  protocol  = "email"
  endpoint  = var.alarm_email
}

resource "aws_cloudwatch_metric_alarm" "collect_errors" {
  alarm_name          = "${var.project}-${var.environment}-scraper-collect-errors"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "1"
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = "86400"
  statistic           = "Sum"
  threshold           = "0"
  alarm_description   = "Falha (Errors) na coleta diária do scraper."
  alarm_actions       = [aws_sns_topic.alarms.arn]
  ok_actions          = [aws_sns_topic.alarms.arn]
  treat_missing_data  = "notBreaching"
  dimensions = {
    FunctionName = aws_lambda_function.collect.function_name
  }
}
