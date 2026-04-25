/*
  TERRAFORM OUTPUTS
  ==================
  Outputs display important values after terraform apply completes.
  They're also accessible to other Terraform configurations and CI/CD.
*/

output "s3_bucket_name" {
  description = "S3 bucket for anomaly results"
  value       = aws_s3_bucket.anomaly_results.id
}

output "s3_bucket_arn" {
  description = "S3 bucket ARN"
  value       = aws_s3_bucket.anomaly_results.arn
}

output "sns_topic_arn" {
  description = "SNS topic ARN for anomaly alerts"
  value       = aws_sns_topic.anomaly_alerts.arn
}

output "lambda_function_name" {
  description = "Lambda function name"
  value       = aws_lambda_function.anomaly_detector.function_name
}

output "lambda_function_arn" {
  description = "Lambda function ARN"
  value       = aws_lambda_function.anomaly_detector.arn
}

output "cloudwatch_log_group" {
  description = "CloudWatch log group for application logs"
  value       = aws_cloudwatch_log_group.app_logs.name
}
