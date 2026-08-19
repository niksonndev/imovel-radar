# GitHub OIDC — o provider deve existir na conta (criado uma vez no bootstrap).
data "aws_iam_openid_connect_provider" "github" {
  url = "https://token.actions.githubusercontent.com"
}

data "aws_iam_policy_document" "github_actions_trust" {
  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]
    principals {
      type        = "Federated"
      identifiers = [data.aws_iam_openid_connect_provider.github.arn]
    }
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }
    condition {
      test     = "StringLike"
      variable = "token.actions.githubusercontent.com:sub"
      values   = ["repo:${var.github_repo}:ref:refs/heads/main"]
    }
  }
}

resource "aws_iam_role" "github_actions" {
  name               = "${var.project}-${var.environment}-gha-deploy"
  assume_role_policy = data.aws_iam_policy_document.github_actions_trust.json
}

data "aws_iam_policy_document" "github_actions_deploy" {
  statement {
    sid = "S3StateAndArtifacts"
    actions = [
      "s3:GetObject", "s3:PutObject", "s3:DeleteObject",
      "s3:ListBucket", "s3:GetBucketVersioning",
    ]
    resources = [
      "arn:aws:s3:::${var.artifact_bucket}",
      "arn:aws:s3:::${var.artifact_bucket}/*",
      "arn:aws:s3:::${var.state_bucket}",
      "arn:aws:s3:::${var.state_bucket}/${var.state_key}",
      "arn:aws:s3:::${var.state_bucket}/${var.state_key}.tflock",
    ]
  }

  statement {
    sid = "LambdaFunctionAndCode"
    actions = [
      "lambda:GetFunctionConfiguration", "lambda:UpdateFunctionCode",
      "lambda:UpdateFunctionConfiguration", "lambda:InvokeFunction",
      "lambda:CreateFunction", "lambda:DeleteFunction", "lambda:GetPolicy",
      "lambda:AddPermission", "lambda:RemovePermission",
    ]
    resources = [
      "arn:aws:lambda:${var.region}:*:function:${var.project}-${var.environment}-scraper-collect",
    ]
  }

  statement {
    sid = "EventBridgeRule"
    actions = [
      "events:PutRule", "events:PutTargets", "events:DescribeRule",
      "events:DeleteRule", "events:RemoveTargets",
    ]
    resources = [
      "arn:aws:events:${var.region}:*:rule/${var.project}-${var.environment}-scraper-collect-cron",
    ]
  }

  statement {
    sid     = "SsmSecret"
    actions = ["ssm:PutParameter", "ssm:GetParameter", "ssm:DeleteParameter"]
    resources = [
      "arn:aws:ssm:${var.region}:*:parameter/${var.project}/${var.environment}/database_url",
    ]
  }

  statement {
    sid = "CloudWatchLogsAndAlarm"
    actions = [
      "logs:CreateLogGroup", "logs:PutRetentionPolicy", "logs:DeleteLogGroup",
      "logs:CreateLogStream", "logs:PutLogEvents", "logs:DeleteLogStream",
      "cloudwatch:PutMetricAlarm", "cloudwatch:DeleteAlarms",
      "cloudwatch:DescribeAlarms",
    ]
    resources = [
      "arn:aws:logs:${var.region}:*:log-group:/aws/lambda/${var.project}-${var.environment}-scraper-collect",
      "arn:aws:logs:${var.region}:*:log-group:/aws/lambda/${var.project}-${var.environment}-scraper-collect:log-stream:*",
      "arn:aws:cloudwatch:${var.region}:*:alarm:${var.project}-${var.environment}-scraper-collect-*",
    ]
  }

  statement {
    sid = "IAMRolesForProject"
    actions = [
      "iam:CreateRole", "iam:GetRole", "iam:DeleteRole", "iam:TagRole",
      "iam:GetRolePolicy", "iam:PutRolePolicy", "iam:DeleteRolePolicy",
      "iam:AttachRolePolicy", "iam:DetachRolePolicy",
      "iam:ListAttachedRolePolicies", "iam:CreatePolicy", "iam:GetPolicy",
      "iam:DeletePolicy", "iam:ListPolicies",
    ]
    resources = [
      "arn:aws:iam::*:role/${var.project}-${var.environment}-scraper-collect",
      "arn:aws:iam::*:role/${var.project}-${var.environment}-gha-deploy",
      "arn:aws:iam::*:policy/${var.project}-${var.environment}-scraper-collect-ssm",
    ]
  }

  statement {
    sid     = "IAMPassRoleForLambda"
    actions = ["iam:PassRole"]
    resources = [
      "arn:aws:iam::*:role/${var.project}-${var.environment}-scraper-collect",
    ]
    condition {
      test     = "StringEquals"
      variable = "iam:PassedToService"
      values   = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_policy" "github_actions_deploy" {
  name        = "${var.project}-${var.environment}-gha-deploy"
  description = "Permissões de deploy via GitHub Actions (scraper Lambda)"
  policy      = data.aws_iam_policy_document.github_actions_deploy.json
}

resource "aws_iam_role_policy_attachment" "github_actions_deploy" {
  role       = aws_iam_role.github_actions.name
  policy_arn = aws_iam_policy.github_actions_deploy.arn
}

resource "aws_iam_role_policy_attachment" "github_actions_admin" {
  role       = aws_iam_role.github_actions.name
  policy_arn = "arn:aws:iam::aws:policy/AdministratorAccess"
}
