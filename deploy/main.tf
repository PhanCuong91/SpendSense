terraform {
  required_version = ">= 1.0.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

data "aws_caller_identity" "current" {}

locals {
  common_tags = {
    Project = var.project_name
    Managed = "terraform"
  }
}

# ======================================================
#  ECR REPOSITORY
# ======================================================

resource "aws_ecr_repository" "app" {
  name                 = var.ecr_repo_name
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  encryption_configuration {
    encryption_type = "AES256"
  }

  tags = local.common_tags
}

resource "aws_ecr_lifecycle_policy" "app_policy" {
  repository = aws_ecr_repository.app.name

  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Keep last N images"
        selection = {
          tagStatus   = "any"
          countType   = "imageCountMoreThan"
          countNumber = var.lifecycle_keep
        }
        action = { type = "expire" }
      }
    ]
  })
}

# ======================================================
#  SECRETS MANAGER (Gmail)
# ======================================================

resource "aws_secretsmanager_secret" "gmail_credentials" {
  name = "${var.project_name}_gmail_credentials_json"
  tags = local.common_tags
}

resource "aws_secretsmanager_secret_version" "gmail_credentials_version" {
  secret_id     = aws_secretsmanager_secret.gmail_credentials.id
  secret_string = file("${path.module}/gmail/credentials.json")
}

resource "aws_secretsmanager_secret" "gmail_token" {
  name = "${var.project_name}_gmail_token_json"
  tags = local.common_tags
}

resource "aws_secretsmanager_secret_version" "gmail_token_version" {
  secret_id     = aws_secretsmanager_secret.gmail_token.id
  secret_string = file("${path.module}/gmail/token.json")
}

# ======================================================
#  EFS (SQLite)
# ======================================================

resource "aws_efs_file_system" "app_fs" {
  encrypted      = true
  creation_token = "${var.project_name}-sqlite-fs"
  tags           = local.common_tags
}

resource "aws_security_group" "efs_sg" {
  name        = "${var.project_name}-efs-sg"
  description = "Allow NFS from app EC2"
  vpc_id      = var.vpc_id

  ingress {
    from_port       = 2049
    to_port         = 2049
    protocol        = "tcp"
    security_groups = [aws_security_group.ec2_sg.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = local.common_tags
}

resource "aws_efs_mount_target" "mt" {
  count           = length(var.private_subnets)
  file_system_id  = aws_efs_file_system.app_fs.id
  subnet_id       = var.private_subnets[count.index]
  security_groups = [aws_security_group.efs_sg.id]
}

resource "aws_efs_access_point" "ec2_ap" {
  file_system_id = aws_efs_file_system.app_fs.id

  posix_user {
    uid = 1000
    gid = 1000
  }

  root_directory {
    path = "/spendsense"
    creation_info {
      owner_uid   = 1000
      owner_gid   = 1000
      permissions = "0755"
    }
  }

  tags = local.common_tags
}

# ======================================================
#  EC2 HOST (RUNS API + WORKERS)
# ======================================================

resource "aws_security_group" "ec2_sg" {
  name        = "${var.project_name}-ec2-sg"
  description = "Allow API ingress"
  vpc_id      = var.vpc_id

  ingress {
    from_port   = 8000
    to_port     = 8000
    protocol    = "tcp"
    cidr_blocks = [var.api_ingress_cidr]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = local.common_tags
}

resource "aws_iam_role" "ec2_role" {
  name = "${var.project_name}-ec2-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "ec2.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })

  tags = local.common_tags
}

resource "aws_iam_role_policy_attachment" "ec2_ecr_read" {
  role       = aws_iam_role.ec2_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly"
}

resource "aws_iam_role_policy_attachment" "ec2_ssm" {
  role       = aws_iam_role.ec2_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_instance_profile" "ec2_profile" {
  name = "${var.project_name}-ec2-profile"
  role = aws_iam_role.ec2_role.name
}

data "aws_ssm_parameter" "al2023_ami" {
  name = "/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64"
}

resource "aws_instance" "app_host" {
  ami                         = data.aws_ssm_parameter.al2023_ami.value
  instance_type               = var.ec2_instance_type
  subnet_id                   = var.public_subnet_id
  vpc_security_group_ids      = [aws_security_group.ec2_sg.id]
  iam_instance_profile        = aws_iam_instance_profile.ec2_profile.name
  associate_public_ip_address = true

  user_data = templatefile("${path.module}/user_data.sh.tftpl", {
    aws_region   = var.aws_region
    efs_id       = aws_efs_file_system.app_fs.id
    ecr_registry = "${data.aws_caller_identity.current.account_id}.dkr.ecr.${var.aws_region}.amazonaws.com"
    ecr_repo_url = aws_ecr_repository.app.repository_url
    app_version  = var.app_version
    database_url = "sqlite:////mnt/efs/txdb.sqlite3"
  })

  tags = merge(local.common_tags, {
    Name = "${var.project_name}-host"
  })

  depends_on = [aws_efs_mount_target.mt]
}

# ======================================================
#  IAM ROLE FOR START/STOP LAMBDAS
# ======================================================

resource "aws_iam_role" "lambda_exec_role" {
  name = "${var.project_name}-lambda-ec2-control"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Action    = "sts:AssumeRole"
      Principal = { Service = "lambda.amazonaws.com" }
    }]
  })

  tags = local.common_tags
}

resource "aws_iam_role_policy" "lambda_policy" {
  role = aws_iam_role.lambda_exec_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "ec2:StartInstances",
          "ec2:StopInstances"
        ]
        Resource = aws_instance.app_host.arn
      },
      {
        Effect   = "Allow"
        Action   = ["ec2:DescribeInstances"]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "*"
      }
    ]
  })
}

# ======================================================
#  START/STOP LAMBDAS
# ======================================================

data "archive_file" "start_zip" {
  type        = "zip"
  source_file = "${path.module}/lambda/start_apprunner.py"
  output_path = "${path.module}/lambda/start_apprunner.zip"
}

resource "aws_lambda_function" "start_ec2" {
  function_name = "${var.project_name}-start-ec2"
  handler       = "start_apprunner.lambda_handler"
  runtime       = "python3.11"
  role          = aws_iam_role.lambda_exec_role.arn
  filename      = data.archive_file.start_zip.output_path
  timeout       = 30

  environment {
    variables = {
      EC2_INSTANCE_ID = aws_instance.app_host.id
    }
  }

  tags = local.common_tags
}

data "archive_file" "stop_zip" {
  type        = "zip"
  source_file = "${path.module}/lambda/stop_apprunner.py"
  output_path = "${path.module}/lambda/stop_apprunner.zip"
}

resource "aws_lambda_function" "stop_ec2" {
  function_name = "${var.project_name}-stop-ec2"
  handler       = "stop_apprunner.lambda_handler"
  runtime       = "python3.11"
  role          = aws_iam_role.lambda_exec_role.arn
  filename      = data.archive_file.stop_zip.output_path
  timeout       = 30

  environment {
    variables = {
      EC2_INSTANCE_ID = aws_instance.app_host.id
    }
  }

  tags = local.common_tags
}

# ======================================================
#  EVENTBRIDGE SCHEDULES (RUN 15 MINUTES/DAY)
# ======================================================

resource "aws_cloudwatch_event_rule" "start_daily" {
  name                = "${var.project_name}-start-daily"
  schedule_expression = "cron(${var.schedule_start_cron_utc})"
}

resource "aws_cloudwatch_event_target" "start_target" {
  rule      = aws_cloudwatch_event_rule.start_daily.name
  target_id = "startEc2"
  arn       = aws_lambda_function.start_ec2.arn
}

resource "aws_lambda_permission" "start_perm" {
  statement_id  = "AllowStartInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.start_ec2.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.start_daily.arn
}

resource "aws_cloudwatch_event_rule" "stop_daily" {
  name                = "${var.project_name}-stop-daily"
  schedule_expression = "cron(${var.schedule_stop_cron_utc})"
}

resource "aws_cloudwatch_event_target" "stop_target" {
  rule      = aws_cloudwatch_event_rule.stop_daily.name
  target_id = "stopEc2"
  arn       = aws_lambda_function.stop_ec2.arn
}

resource "aws_lambda_permission" "stop_perm" {
  statement_id  = "AllowStopInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.stop_ec2.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.stop_daily.arn
}
