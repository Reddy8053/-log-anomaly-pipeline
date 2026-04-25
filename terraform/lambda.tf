/*
  LAMBDA TERRAFORM CONFIGURATION
  ================================
  This file defines everything the Lambda function needs:
  
  1. IAM Role          — "Who is the Lambda allowed to be?"
  2. IAM Policies      — "What is the Lambda allowed to do?"
  3. Lambda Function   — The actual function resource
  4. CloudWatch Log Group — Where the app logs go
  5. Subscription Filter — The trigger that connects logs → Lambda
  6. Lambda Permission  — Allows CloudWatch to invoke the Lambda
  
  IAM EXPLAINED:
  IAM (Identity and Access Management) follows the Principle of Least
  Privilege — each resource gets ONLY the permissions it needs.
  
  The Lambda needs to:
    ✅ Read from CloudWatch Logs  (to get log events)
    ✅ Write to S3                (to store anomaly reports)
    ✅ Publish to SNS             (to send alerts)
    ✅ Write its own logs          (to CloudWatch for debugging)
    ❌ Everything else is DENIED by default
*/

# ──────────────────────────────────────────────
# IAM Role: Lambda's identity
# ──────────────────────────────────────────────
# The "assume role policy" says: only AWS Lambda service can use this role
resource "aws_iam_role" "lambda_role" {
  name = "${var.project_name}-lambda-role-${var.environment}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })
}

# ──────────────────────────────────────────────
# IAM Policy: What the Lambda can do
# ──────────────────────────────────────────────
resource "aws_iam_role_policy" "lambda_policy" {
  name = "${var.project_name}-lambda-policy-${var.environment}"
  role = aws_iam_role.lambda_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        # Permission to write CloudWatch Logs (Lambda's own logs)
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:*:*:*"
      },
      {
        # Permission to write anomaly reports to S3
        Effect = "Allow"
        Action = [
          "s3:PutObject",
          "s3:GetObject"
        ]
        Resource = "${aws_s3_bucket.anomaly_results.arn}/*"
      },
      {
        # Permission to publish alerts to SNS
        Effect = "Allow"
        Action = [
          "sns:Publish"
        ]
        Resource = aws_sns_topic.anomaly_alerts.arn
      }
    ]
  })
}

# ──────────────────────────────────────────────
# Lambda Function: The anomaly detector
# ──────────────────────────────────────────────
# The function code is packaged as a ZIP and uploaded.
# The model is packaged as a Lambda Layer (mounted at /opt/).
data "archive_file" "lambda_zip" {
  type        = "zip"
  source_dir  = "${path.module}/../src"
  output_path = "${path.module}/lambda_package.zip"
}

resource "aws_lambda_function" "anomaly_detector" {
  filename         = data.archive_file.lambda_zip.output_path
  function_name    = "${var.project_name}-detector-${var.environment}"
  role            = aws_iam_role.lambda_role.arn
  handler         = "lambda_function.handler"
  runtime         = "python3.11"
  timeout         = var.lambda_timeout
  memory_size     = var.lambda_memory
  source_code_hash = data.archive_file.lambda_zip.output_base64sha256

  environment {
    variables = {
      S3_BUCKET     = aws_s3_bucket.anomaly_results.id
      SNS_TOPIC_ARN = aws_sns_topic.anomaly_alerts.arn
      MODEL_PATH    = "/opt/model/isolation_forest.joblib"
      ENVIRONMENT   = var.environment
    }
  }

  tags = {
    Name = "Anomaly Detection Lambda"
  }
}

# ──────────────────────────────────────────────
# CloudWatch Log Group: Where app logs are sent
# ──────────────────────────────────────────────
# In a real setup, your application sends logs here.
# The subscription filter watches this log group and
# triggers the Lambda whenever new logs arrive.
resource "aws_cloudwatch_log_group" "app_logs" {
  name              = "/app/${var.project_name}-${var.environment}"
  retention_in_days = 30

  tags = {
    Name = "Application Logs"
  }
}

# Lambda's own log group (for debugging the Lambda itself)
resource "aws_cloudwatch_log_group" "lambda_logs" {
  name              = "/aws/lambda/${aws_lambda_function.anomaly_detector.function_name}"
  retention_in_days = 14
}

# ──────────────────────────────────────────────
# Subscription Filter: Connects logs → Lambda
# ──────────────────────────────────────────────
# This is the GLUE that makes the pipeline work.
# filter_pattern = "" means ALL log events trigger the Lambda.
# You could use patterns like "ERROR" to only trigger on errors.
resource "aws_cloudwatch_log_subscription_filter" "lambda_trigger" {
  name            = "${var.project_name}-trigger-${var.environment}"
  log_group_name  = aws_cloudwatch_log_group.app_logs.name
  filter_pattern  = ""
  destination_arn = aws_lambda_function.anomaly_detector.arn

  depends_on = [aws_lambda_permission.cloudwatch]
}

# ──────────────────────────────────────────────
# Lambda Permission: Allow CloudWatch to invoke
# ──────────────────────────────────────────────
# Without this, CloudWatch would get "Access Denied" when trying
# to trigger the Lambda. This is AWS's way of saying:
# "Yes, CloudWatch Logs is allowed to call this specific Lambda."
resource "aws_lambda_permission" "cloudwatch" {
  statement_id  = "AllowCloudWatchInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.anomaly_detector.function_name
  principal     = "logs.amazonaws.com"
  source_arn    = "${aws_cloudwatch_log_group.app_logs.arn}:*"
}
