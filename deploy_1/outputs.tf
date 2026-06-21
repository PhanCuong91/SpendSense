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
