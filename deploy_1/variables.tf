variable "aws_region" {
  description = "AWS region to deploy into."
  type        = string
  default     = "ap-southeast-1"
}

variable "project_name" {
  description = "Base name for created resources."
  type        = string
  default     = "spendsense"
}

variable "ecr_repo_name" {
  description = "Name of the ECR repository for the container image."
  type        = string
  default     = "spend_sense"
}

variable "app_image_tag" {
  description = "Image tag to run from ECR."
  type        = string
  default     = "1.0.9"
}

variable "app_container_name" {
  description = "Name of the ECS container definition."
  type        = string
  default     = "spendsense"
}


variable "efs_root_path" {
  description = "Root directory path created on the EFS access point."
  type        = string
  default     = "/spendsense"
}

variable "db_mount_path" {
  description = "Container path where the EFS volume is mounted."
  type        = string
  default     = "/app/data"
}

variable "db_file_path" {
  description = "Path inside the container where SQLite database file is stored."
  type        = string
  default     = "sqlite:///./data/txdb.sqlite3"
}

variable "db_backup_bucket" {
  description = "S3 bucket used by the backup ECS task to store the SQLite database."
  type        = string
  default     = "spensense-db-359615771071-ap-southeast-1-an"
}

variable "db_backup_key" {
  description = "S3 object key used by the backup ECS task to store the SQLite database."
  type        = string
  default     = "txdb.sqlite3"
}

variable "backup_task_cpu" {
  description = "CPU allocation for the one-off backup ECS task."
  type        = string
  default     = "512"
}

variable "backup_task_memory" {
  description = "Memory allocation for the one-off backup ECS task (MiB)."
  type        = string
  default     = "1024"
}

variable "backup_container_image_tag" {
  description = "Container image used for the one-off backup ECS task."
  type        = string
  default     = "backup-efs-amd64"
}

variable "schedule_start_expression" {
  description = "CloudWatch cron expression to start the ECS service. Uses UTC timezone."
  type        = string
  default     = "cron(00 14 * * ? *)"
}

variable "schedule_stop_expression" {
  description = "CloudWatch cron expression to stop the ECS service after the run window. Uses UTC timezone; defaults to 22:20 SGP / 14:20 UTC."
  type        = string
  default     = "cron(20 14 * * ? *)"
}

variable "task_cpu" {
  description = "Fargate task CPU allocation."
  type        = string
  default     = "512"
}

variable "task_memory" {
  description = "Fargate task memory allocation (MiB)."
  type        = string
  default     = "1024"
}

variable "enable_schedule" {
  description = "Enable daily start/stop schedules for the ECS service. Set false for always-on testing."
  type        = bool
  default     = true
}

variable "gmail_credentials_file" {
  description = "Path to the Gmail credentials JSON file used to populate Secrets Manager."
  type        = string
  default     = "../credentials.json"
}

variable "gmail_token_file" {
  description = "Path to the Gmail token JSON file used to populate Secrets Manager."
  type        = string
  default     = "../token.json"
}

variable "gmail_credentials_json" {
  type        = string
  default     = null
  description = "Gmail credentials JSON content (from GitHub Actions secret). If not provided, reads from local file."
  sensitive   = true
}

variable "gmail_token_json" {
  type        = string
  default     = null
  description = "Gmail token JSON content (from GitHub Actions secret). If not provided, reads from local file."
  sensitive   = true
}

variable "vpc_id" {
  type        = string
  description = "VPC where EC2/EFS will be deployed"
  default     = "vpc-0e67ef7841be38480"
}


variable "private_subnet_ids" {
  type        = list(string)
  description = "Private subnets for EFS mount targets"
  default     = ["subnet-055480c6716bfb03a"]
}

variable "public_subnet_ids" {
  type        = list(string)
  description = "Public subnets for ECS tasks that require a public IP for outbound internet access. If empty, falls back to private_subnet_ids."
  default     = []
}