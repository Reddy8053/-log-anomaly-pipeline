/*
  MAIN TERRAFORM CONFIGURATION
  =============================
  This file defines the core infrastructure:
  
  1. AWS Provider   — tells Terraform which cloud and region to use
  2. S3 Bucket      — stores anomaly detection results as JSON files
  3. SNS Topic      — sends email alerts when anomalies are detected
  4. SNS Subscription — connects an email address to the topic
  
  WHAT IS TERRAFORM?
  Terraform is an Infrastructure as Code (IaC) tool. Instead of clicking
  through the AWS Console, you DECLARE what resources you want in .tf files.
  Terraform then:
    1. Plans — shows you what it WILL create/change/destroy
    2. Applies — actually creates the resources in AWS
    3. Tracks — saves state so it knows what exists
*/

# ──────────────────────────────────────────────
# Provider: Which cloud, which region
# ──────────────────────────────────────────────
terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # For a real project, use remote state (S3 backend):
  # backend "s3" {
  #   bucket = "your-terraform-state-bucket"
  #   key    = "log-anomaly/terraform.tfstate"
  #   region = "us-east-1"
  # }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = var.project_name
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}

# ──────────────────────────────────────────────
# S3 Bucket: Stores anomaly detection results
# ──────────────────────────────────────────────
# The Lambda writes JSON reports here whenever anomalies are detected.
# Grafana reads from this bucket to populate dashboards.
resource "aws_s3_bucket" "anomaly_results" {
  bucket = "${var.project_name}-results-${var.environment}"

  tags = {
    Name = "Anomaly Detection Results"
  }
}

# Enable versioning — keeps history of all anomaly reports
resource "aws_s3_bucket_versioning" "anomaly_results" {
  bucket = aws_s3_bucket.anomaly_results.id
  versioning_configuration {
    status = "Enabled"
  }
}

# Server-side encryption — encrypt data at rest
resource "aws_s3_bucket_server_side_encryption_configuration" "anomaly_results" {
  bucket = aws_s3_bucket.anomaly_results.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# Lifecycle rule — auto-delete old reports after 90 days
resource "aws_s3_bucket_lifecycle_configuration" "anomaly_results" {
  bucket = aws_s3_bucket.anomaly_results.id

  rule {
    id     = "cleanup-old-reports"
    status = "Enabled"

    expiration {
      days = 90
    }
  }
}

# ──────────────────────────────────────────────
# SNS Topic: Sends alert notifications
# ──────────────────────────────────────────────
# When the Lambda detects anomalies, it publishes a message to this topic.
# All subscribers (email, Slack webhook, PagerDuty, etc.) get notified.
resource "aws_sns_topic" "anomaly_alerts" {
  name = "${var.project_name}-alerts-${var.environment}"

  tags = {
    Name = "Anomaly Detection Alerts"
  }
}

# Email subscription (only if alert_email is provided)
resource "aws_sns_topic_subscription" "email_alert" {
  count     = var.alert_email != "" ? 1 : 0
  topic_arn = aws_sns_topic.anomaly_alerts.arn
  protocol  = "email"
  endpoint  = var.alert_email
}
