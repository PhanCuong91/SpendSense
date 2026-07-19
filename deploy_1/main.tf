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

  ecs_subnet_ids = length(var.public_subnet_ids) > 0 ? var.public_subnet_ids : var.private_subnet_ids
}

resource "aws_ecr_repository" "app" {
  name                 = var.ecr_repo_name
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = local.common_tags
}

resource "aws_secretsmanager_secret" "gmail_credentials" {
  name = "${var.project_name}_gmail_credentials_json"
  tags = local.common_tags
}

resource "aws_secretsmanager_secret_version" "gmail_credentials_version" {
  secret_id     = aws_secretsmanager_secret.gmail_credentials.id
  secret_string = var.gmail_credentials_json != null ? var.gmail_credentials_json : file(var.gmail_credentials_file)
}

resource "aws_secretsmanager_secret" "gmail_token" {
  name = "${var.project_name}_gmail_token_json"
  tags = local.common_tags
}

resource "aws_secretsmanager_secret_version" "gmail_token_version" {
  secret_id     = aws_secretsmanager_secret.gmail_token.id
  secret_string = var.gmail_token_json != null ? var.gmail_token_json : file(var.gmail_token_file)
}

resource "aws_efs_file_system" "app_fs" {
  encrypted      = true
  creation_token = "${var.project_name}-efs-fs"
  tags           = local.common_tags
}

resource "aws_security_group" "ecs_sg" {
  name        = "${var.project_name}-ecs-sg"
  description = "ECS task security group"
  vpc_id      = var.vpc_id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = local.common_tags
}

resource "aws_security_group" "efs_sg" {
  name        = "${var.project_name}-efs-sg"
  description = "Allow NFS from ECS tasks"
  vpc_id      = var.vpc_id

  ingress {
    from_port       = 2049
    to_port         = 2049
    protocol        = "tcp"
    security_groups = [aws_security_group.ecs_sg.id]
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
  count           = length(local.ecs_subnet_ids)
  file_system_id  = aws_efs_file_system.app_fs.id
  subnet_id       = local.ecs_subnet_ids[count.index]
  security_groups = [aws_security_group.efs_sg.id]
}

resource "aws_efs_access_point" "app_ap" {
  file_system_id = aws_efs_file_system.app_fs.id

  posix_user {
    uid = 1000
    gid = 1000
  }

  root_directory {
    path = var.efs_root_path
    creation_info {
      owner_uid   = 1000
      owner_gid   = 1000
      permissions = "0755"
    }
  }

  tags = local.common_tags
}

resource "aws_cloudwatch_log_group" "ecs_logs" {
  name              = "/ecs/${var.project_name}"
  retention_in_days = 14
  tags              = local.common_tags
}

resource "aws_iam_role" "ecs_task_execution_role" {
  name = "${var.project_name}-ecs-execution-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ecs-tasks.amazonaws.com"
        }
      }
    ]
  })

  tags = local.common_tags
}

resource "aws_iam_role_policy_attachment" "ecs_task_execution" {
  role       = aws_iam_role.ecs_task_execution_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role_policy" "ecs_task_secrets_policy" {
  role = aws_iam_role.ecs_task_execution_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue",
          "kms:Decrypt"
        ]
        Resource = [
          aws_secretsmanager_secret.gmail_credentials.arn,
          aws_secretsmanager_secret.gmail_token.arn
        ]
      }
    ]
  })
}

resource "aws_iam_role" "ecs_task_role" {
  name = "${var.project_name}-ecs-task-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ecs-tasks.amazonaws.com"
        }
      }
    ]
  })

  tags = local.common_tags
}

resource "aws_iam_role_policy" "ecs_task_s3_policy" {
  role = aws_iam_role.ecs_task_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:ListBucket"
        ]
        Resource = "arn:aws:s3:::${var.db_backup_bucket}"
      },
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject"
        ]
        Resource = "arn:aws:s3:::${var.db_backup_bucket}/${var.db_backup_key}"
      },
      {
        Effect = "Allow"
        Action = [
          "s3:PutObject"
        ]
        Resource = "arn:aws:s3:::${var.db_backup_bucket}/${var.db_backup_key}"
      }
    ]
  })
}

resource "aws_ecs_cluster" "app_cluster" {
  name = "${var.project_name}-cluster"
  tags = local.common_tags
}

resource "aws_ecs_task_definition" "app_task" {
  family                   = "${var.project_name}-task"
  cpu                      = var.task_cpu
  memory                   = var.task_memory
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  execution_role_arn       = aws_iam_role.ecs_task_execution_role.arn
  task_role_arn            = aws_iam_role.ecs_task_role.arn

  volume {
    name = "efs-data"

    efs_volume_configuration {
      file_system_id = aws_efs_file_system.app_fs.id
      authorization_config {
        access_point_id = aws_efs_access_point.app_ap.id
        iam             = "DISABLED"
      }
      transit_encryption = "ENABLED"
    }
  }

  container_definitions = jsonencode([
    {
      name      = var.app_container_name
      image     = "${aws_ecr_repository.app.repository_url}:${var.app_image_tag}"
      essential = true

      environment = [
        {
          name  = "DATABASE_URL"
          value = "${var.db_file_path}"
        }
      ]

      secrets = [
        {
          name      = "GMAIL_CREDENTIALS_JSON"
          valueFrom = aws_secretsmanager_secret.gmail_credentials.arn
        },
        {
          name      = "GMAIL_TOKEN_JSON"
          valueFrom = aws_secretsmanager_secret.gmail_token.arn
        }
      ]

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.ecs_logs.name
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = var.project_name
        }
      }

      command = [
        "/bin/sh",
        "-c",
        "mkdir -p ${var.db_mount_path} && if [ ! -f ${var.db_mount_path}/txdb.sqlite3 ] || [ ! -s ${var.db_mount_path}/txdb.sqlite3 ]; then python - <<'PY'\nimport os\nimport boto3\nfrom botocore.config import Config\nfrom pathlib import Path\n\nbucket = '${var.db_backup_bucket}'\nkey = '${var.db_backup_key}'\ndest = Path('${var.db_mount_path}') / 'txdb.sqlite3'\ndest.parent.mkdir(parents=True, exist_ok=True)\ns3 = boto3.client('s3', config=Config(signature_version='s3v4'))\ns3.download_file(bucket, key, str(dest))\nPY\nfi && exec python -m app.workers.poller_worker --host 0.0.0.0 --port 8000"
      ]

      mountPoints = [
        {
          sourceVolume  = "efs-data"
          containerPath = var.db_mount_path
          readOnly      = false
        }
      ]
    }
  ])
}

resource "aws_ecs_task_definition" "backup_task" {
  family                   = "${var.project_name}-backup-task"
  cpu                      = var.backup_task_cpu
  memory                   = var.backup_task_memory
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  execution_role_arn       = aws_iam_role.ecs_task_execution_role.arn
  task_role_arn            = aws_iam_role.ecs_task_role.arn

  volume {
    name = "efs-data"

    efs_volume_configuration {
      file_system_id = aws_efs_file_system.app_fs.id
      authorization_config {
        access_point_id = aws_efs_access_point.app_ap.id
        iam             = "DISABLED"
      }
      transit_encryption = "ENABLED"
    }
  }

  container_definitions = jsonencode([
    {
      name      = "${var.project_name}-backup"
      image     = "${aws_ecr_repository.app.repository_url}:${var.backup_container_image_tag}"
      essential = true

      environment = [
        {
          name  = "S3_BUCKET"
          value = var.db_backup_bucket
        },
        {
          name  = "S3_KEY"
          value = var.db_backup_key
        },
        {
          name  = "DB_PATH"
          value = "${var.db_mount_path}/txdb.sqlite3"
        }
      ]

      command = [
        "/bin/sh",
        "-c",
        "set -e; if [ -f ${var.db_mount_path}/txdb.sqlite3 ]; then aws s3 cp ${var.db_mount_path}/txdb.sqlite3 s3://${var.db_backup_bucket}/${var.db_backup_key}; else echo 'Database file not found at ${var.db_mount_path}/txdb.sqlite3' >&2; exit 1; fi"
      ]

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.ecs_logs.name
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "${var.project_name}-backup"
        }
      }

      mountPoints = [
        {
          sourceVolume  = "efs-data"
          containerPath = var.db_mount_path
          readOnly      = false
        }
      ]
    }
  ])
}

resource "aws_iam_role" "eventbridge_ecs_role" {
  name = "${var.project_name}-eventbridge-ecs-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "events.amazonaws.com"
        }
      }
    ]
  })

  tags = local.common_tags
}

resource "aws_iam_role_policy" "eventbridge_ecs_policy" {
  role = aws_iam_role.eventbridge_ecs_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["ecs:RunTask"]
        Resource = [aws_ecs_task_definition.backup_task.arn]
      },
      {
        Effect = "Allow"
        Action = ["iam:PassRole"]
        Resource = [
          aws_iam_role.ecs_task_execution_role.arn,
          aws_iam_role.ecs_task_role.arn
        ]
        Condition = {
          StringLike = {
            "iam:PassedToService" = "ecs-tasks.amazonaws.com"
          }
        }
      }
    ]
  })
}

resource "aws_cloudwatch_event_rule" "app_task_stopped" {
  name        = "${var.project_name}-app-task-stopped"
  description = "Run the database backup task after the main ECS task has stopped"

  event_pattern = jsonencode({
    source      = ["aws.ecs"]
    detail-type = ["ECS Task State Change"]
    detail = {
      lastStatus    = ["STOPPED"]
      desiredStatus = ["STOPPED"]
      clusterArn    = [aws_ecs_cluster.app_cluster.arn]
      group         = ["service:${aws_ecs_service.app_service.name}"]
    }
  })
}

resource "aws_cloudwatch_event_target" "run_backup_task" {
  rule = aws_cloudwatch_event_rule.app_task_stopped.name
  arn  = aws_ecs_cluster.app_cluster.arn

  role_arn = aws_iam_role.eventbridge_ecs_role.arn

  ecs_target {
    launch_type         = "FARGATE"
    task_count          = 1
    task_definition_arn = aws_ecs_task_definition.backup_task.arn
    platform_version    = "1.4.0"

    network_configuration {
      subnets          = local.ecs_subnet_ids
      security_groups  = [aws_security_group.ecs_sg.id]
      assign_public_ip = true
    }
  }
}

resource "aws_ecs_service" "app_service" {
  name             = "${var.project_name}-service"
  cluster          = aws_ecs_cluster.app_cluster.id
  task_definition  = aws_ecs_task_definition.app_task.arn
  desired_count    = var.enable_schedule ? 0 : 1
  launch_type      = "FARGATE"
  platform_version = "1.4.0"

  network_configuration {
    # Use explicit public subnet IDs if provided, otherwise fall back to configured subnets.
    subnets          = local.ecs_subnet_ids
    security_groups  = [aws_security_group.ecs_sg.id]
    assign_public_ip = true
  }

  deployment_minimum_healthy_percent = 0
  deployment_maximum_percent         = 100

  depends_on = [aws_efs_mount_target.mt]
}

resource "aws_appautoscaling_target" "ecs_service_target" {
  max_capacity       = 1
  min_capacity       = 0
  resource_id        = "service/${aws_ecs_cluster.app_cluster.name}/${aws_ecs_service.app_service.name}"
  scalable_dimension = "ecs:service:DesiredCount"
  service_namespace  = "ecs"
}

resource "aws_appautoscaling_scheduled_action" "start_daily" {
  count              = var.enable_schedule ? 1 : 0
  name               = "${var.project_name}-start"
  service_namespace  = "ecs"
  resource_id        = aws_appautoscaling_target.ecs_service_target.resource_id
  scalable_dimension = aws_appautoscaling_target.ecs_service_target.scalable_dimension
  schedule           = var.schedule_start_expression

  scalable_target_action {
    min_capacity = 1
    max_capacity = 1
  }
}

resource "aws_appautoscaling_scheduled_action" "stop_daily" {
  count              = var.enable_schedule ? 1 : 0
  name               = "${var.project_name}-stop"
  service_namespace  = "ecs"
  resource_id        = aws_appautoscaling_target.ecs_service_target.resource_id
  scalable_dimension = aws_appautoscaling_target.ecs_service_target.scalable_dimension
  schedule           = var.schedule_stop_expression

  scalable_target_action {
    min_capacity = 0
    max_capacity = 0
  }
}

# allow tasks to talk to endpoints on TLS
resource "aws_security_group_rule" "ecs_allow_tls_self" {
  type                     = "ingress"
  from_port                = 443
  to_port                  = 443
  protocol                 = "tcp"
  security_group_id        = aws_security_group.ecs_sg.id
  source_security_group_id = aws_security_group.ecs_sg.id
}

# Interface endpoint for Secrets Manager
# The ECS service uses public IP addresses so it can reach ECR, Secrets Manager, and other AWS public services over the internet.
# VPC endpoints are removed to avoid the extra interface endpoint costs.

# Example: Fetching an existing AWS VPC by its tags
# data "aws_vpc" "existing_vpc" {
#   filter {
#     name   = "tag:Name"
#     values = ["production-vpc"]
#   }
# }