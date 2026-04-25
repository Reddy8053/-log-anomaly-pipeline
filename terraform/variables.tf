/*
  TERRAFORM VARIABLES
  ===================
  Variables are inputs to your Terraform configuration.
  They let you customize deployments without changing code.
  
  Usage: Set via terraform.tfvars, CLI flags, or environment variables:
    terraform apply -var="alert_email=you@example.com"
    TF_VAR_alert_email=you@example.com terraform apply
*/

variable "aws_region" {
  description = "AWS region for all resources"
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Name prefix for all resources"
  type        = string
  default     = "log-anomaly"
}

variable "environment" {
  description = "Deployment environment (dev, staging, prod)"
  type        = string
  default     = "dev"
}

variable "alert_email" {
  description = "Email address for SNS anomaly alerts"
  type        = string
  default     = ""
}

variable "lambda_timeout" {
  description = "Lambda function timeout in seconds"
  type        = number
  default     = 60
}

variable "lambda_memory" {
  description = "Lambda function memory in MB"
  type        = number
  default     = 256
}
