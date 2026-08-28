output "ecr_repository_url" {
  description = "ECR repository URL for the application image."
  value       = aws_ecr_repository.app.repository_url
}

output "ecs_cluster_name" {
  description = "Name of the ECS cluster."
  value       = aws_ecs_cluster.app_cluster.name
}

output "ecs_service_name" {
  description = "Name of the ECS service used for scheduling."
  value       = aws_ecs_service.app_service.name
}

output "efs_file_system_id" {
  description = "EFS filesystem ID used for persistent storage."
  value       = aws_efs_file_system.app_fs.id
}

output "gmail_credentials_secret_arn" {
  description = "ARN of the created Gmail credentials secret."
  value       = aws_secretsmanager_secret.gmail_credentials.arn
}

output "gmail_token_secret_arn" {
  description = "ARN of the created Gmail token secret."
  value       = aws_secretsmanager_secret.gmail_token.arn
}

output "misa_runner_launch_template_id" {
  description = "ID of the MISA import runner EC2 launch template."
  value       = var.misa_enabled ? aws_launch_template.misa_runner[0].id : null
}

output "misa_runner_security_group_id" {
  description = "Security group ID of the MISA import runner."
  value       = var.misa_enabled ? aws_security_group.misa_runner_sg[0].id : null
}

output "misa_log_group_name" {
  description = "CloudWatch log group for the MISA import runner."
  value       = aws_cloudwatch_log_group.misa_logs.name
}

output "misa_username_ssm_param_name" {
  description = "Name of the MISA username SSM parameter. Populate the value outside Terraform."
  value       = var.misa_enabled ? aws_ssm_parameter.misa_username[0].name : null
}

output "misa_password_ssm_param_name" {
  description = "Name of the MISA password SSM parameter. Populate the value outside Terraform."
  value       = var.misa_enabled ? aws_ssm_parameter.misa_password[0].name : null
}

output "misa_alerts_sns_topic_arn" {
  description = "ARN of the SNS topic for MISA alerts."
  value       = var.misa_enabled ? aws_sns_topic.misa_alerts[0].arn : null
}

output "misa_import_failed_alarm_arn" {
  description = "ARN of the CloudWatch alarm for MISA import failures."
  value       = var.misa_enabled ? aws_cloudwatch_metric_alarm.misa_import_failed_alarm[0].arn : null
}

