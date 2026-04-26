variable "project_name" {
  description = "Project prefix for AWS resources"
  type        = string
  default     = "spendsense"
}

variable "aws_region" {
  type    = string
  default = "ap-southeast-1"
}

variable "ecr_repo_name" {
  type    = string
  default = "fastapi-app"
}

variable "app_version" {
  description = "Image tag to run on EC2, e.g. 1.0.0"
  type        = string
  default     = "dev"
}

variable "lifecycle_keep" {
  type    = number
  default = 5
}

variable "vpc_id" {
  type        = string
  description = "VPC where EC2/EFS will be deployed"
}

variable "public_subnet_id" {
  type        = string
  description = "Public subnet for EC2 host"
}

variable "private_subnets" {
  type        = list(string)
  description = "Private subnets for EFS mount targets"
}

variable "ec2_instance_type" {
  type    = string
  default = "t3.small"
}

variable "api_ingress_cidr" {
  description = "CIDR allowed to access FastAPI on port 8000"
  type        = string
  default     = "0.0.0.0/0"
}

variable "schedule_start_cron_utc" {
  description = "Daily UTC cron for EC2 start"
  type        = string
  default     = "0 18 * * ? *"
}

variable "schedule_stop_cron_utc" {
  description = "Daily UTC cron for EC2 stop (15 minutes after start by default)"
  type        = string
  default     = "15 18 * * ? *"
}
