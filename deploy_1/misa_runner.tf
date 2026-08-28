# =============================================================================
# MISA Import Runner - On-Demand AWS ECS Fargate Task
# See ai/update_misa_implementation/misa_deployment_design.md for full design.
# =============================================================================

# -----------------------------------------------------------------------------
# SSM Parameter Store (Free Tier SecureString for MISA Credentials)
# -----------------------------------------------------------------------------

resource "aws_ssm_parameter" "misa_username" {
  count       = var.misa_enabled ? 1 : 0
  name        = "/${var.project_name}/misa_username"
  description = "MISA Money Keeper login username / email"
  type        = "SecureString"
  value       = "placeholder"
  tags        = local.common_tags

  lifecycle {
    ignore_changes = [value]
  }
}

resource "aws_ssm_parameter" "misa_password" {
  count       = var.misa_enabled ? 1 : 0
  name        = "/${var.project_name}/misa_password"
  description = "MISA Money Keeper login password"
  type        = "SecureString"
  value       = "placeholder"
  tags        = local.common_tags

  lifecycle {
    ignore_changes = [value]
  }
}

# -----------------------------------------------------------------------------
# CloudWatch Log Group (Direct Real-time Container Logging)
# -----------------------------------------------------------------------------

resource "aws_cloudwatch_log_group" "misa_logs" {
  name              = "/ecs/${var.project_name}-misa"
  retention_in_days = 14
  tags              = local.common_tags
}

# -----------------------------------------------------------------------------
# Security Group for MISA Fargate Task
# -----------------------------------------------------------------------------

resource "aws_security_group" "misa_task_sg" {
  count       = var.misa_enabled ? 1 : 0
  name        = "${var.project_name}-misa-task-sg"
  description = "Security group for the MISA import runner ECS Fargate task"
  vpc_id      = var.vpc_id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(local.common_tags, {
    Name = "${var.project_name}-misa-task-sg"
  })
}

# -----------------------------------------------------------------------------
# IAM Roles for MISA Fargate Task
# -----------------------------------------------------------------------------

resource "aws_iam_role" "misa_task_role" {
  count = var.misa_enabled ? 1 : 0
  name  = "${var.project_name}-misa-task-role"

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

resource "aws_iam_role_policy" "misa_task_policy" {
  count = var.misa_enabled ? 1 : 0
  name  = "${var.project_name}-misa-task-policy"
  role  = aws_iam_role.misa_task_role[0].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "S3BackupAccess"
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject"
        ]
        Resource = "arn:aws:s3:::${var.db_backup_bucket}/${var.db_backup_key}"
      },
      {
        Sid    = "SSMParameterRead"
        Effect = "Allow"
        Action = [
          "ssm:GetParameter",
          "ssm:GetParameters"
        ]
        Resource = [
          aws_ssm_parameter.misa_username[0].arn,
          aws_ssm_parameter.misa_password[0].arn
        ]
      }
    ]
  })
}

# -----------------------------------------------------------------------------
# ECS Fargate Task Definition
# -----------------------------------------------------------------------------

resource "aws_ecs_task_definition" "misa_task" {
  count                    = var.misa_enabled ? 1 : 0
  family                   = "${var.project_name}-misa-task"
  cpu                      = var.misa_task_cpu
  memory                   = var.misa_task_memory
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  execution_role_arn       = aws_iam_role.ecs_task_execution_role.arn
  task_role_arn            = aws_iam_role.misa_task_role[0].arn

  container_definitions = jsonencode([
    {
      name      = "${var.project_name}-misa"
      image     = "${aws_ecr_repository.app.repository_url}:${var.app_image_tag}"
      essential = true

      environment = [
        {
          name  = "PYTHONPATH"
          value = "/app"
        },
        {
          name  = "DATABASE_URL"
          value = "sqlite:///./data/txdb.sqlite3"
        },
        {
          name  = "MISA_USERNAME_PARAM_NAME"
          value = aws_ssm_parameter.misa_username[0].name
        },
        {
          name  = "MISA_PASSWORD_PARAM_NAME"
          value = aws_ssm_parameter.misa_password[0].name
        },
        {
          name  = "S3_BUCKET"
          value = var.db_backup_bucket
        },
        {
          name  = "S3_KEY"
          value = var.db_backup_key
        },
        {
          name  = "AWS_REGION"
          value = var.aws_region
        }
      ]

      command = [
        "/bin/sh",
        "-c",
        "cd /app && set -e && mkdir -p /app/data && python - <<'PY'\nimport os, boto3\nfrom botocore.config import Config\ns3 = boto3.client('s3', region_name='${var.aws_region}', config=Config(signature_version='s3v4'))\ntry:\n    s3.download_file('${var.db_backup_bucket}', '${var.db_backup_key}', '/app/data/txdb.sqlite3')\n    print('Successfully downloaded database from S3')\nexcept Exception as e:\n    print(f'Warning downloading DB from S3: {e}')\nPY\nSTART_DATE=$(date -d 'yesterday' +%Y-%m-%d)\nEND_DATE=$(date +%Y-%m-%d)\npython -m app.misa.runner --start-date \"$START_DATE\" --end-date \"$END_DATE\"\npython - <<'PY'\nimport os, boto3\nfrom botocore.config import Config\ns3 = boto3.client('s3', region_name='${var.aws_region}', config=Config(signature_version='s3v4'))\ns3.upload_file('/app/data/txdb.sqlite3', '${var.db_backup_bucket}', '${var.db_backup_key}')\nprint('Successfully uploaded updated database to S3')\nPY\n"
      ]

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.misa_logs.name
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "misa"
        }
      }
    }
  ])

  tags = local.common_tags
}

# -----------------------------------------------------------------------------
# EventBridge: S3 PutObject -> Run MISA Fargate Task
# -----------------------------------------------------------------------------

resource "aws_cloudwatch_event_rule" "misa_db_backup_arrived" {
  count       = var.misa_enabled ? 1 : 0
  name        = "${var.project_name}-misa-db-backup-arrived"
  description = "Run MISA import task when txdb.sqlite3 is backed up to S3"

  event_pattern = jsonencode({
    source      = ["aws.s3"]
    detail-type = ["Object Created"]
    detail = {
      bucket = {
        name = [var.db_backup_bucket]
      }
      object = {
        key = [var.db_backup_key]
      }
    }
  })
}

resource "aws_iam_role" "eventbridge_misa_ecs_role" {
  count = var.misa_enabled ? 1 : 0
  name  = "${var.project_name}-eventbridge-misa-ecs-role"

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

resource "aws_iam_role_policy" "eventbridge_misa_ecs_policy" {
  count = var.misa_enabled ? 1 : 0
  name  = "${var.project_name}-eventbridge-misa-ecs-policy"
  role  = aws_iam_role.eventbridge_misa_ecs_role[0].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["ecs:RunTask"]
        Resource = [aws_ecs_task_definition.misa_task[0].arn]
      },
      {
        Effect = "Allow"
        Action = ["iam:PassRole"]
        Resource = [
          aws_iam_role.ecs_task_execution_role.arn,
          aws_iam_role.misa_task_role[0].arn
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

resource "aws_cloudwatch_event_target" "misa_task" {
  count     = var.misa_enabled ? 1 : 0
  target_id = "${var.project_name}-misa-task-target"
  arn       = aws_ecs_cluster.app_cluster.arn
  rule      = aws_cloudwatch_event_rule.misa_db_backup_arrived[0].name
  role_arn  = aws_iam_role.eventbridge_misa_ecs_role[0].arn

  ecs_target {
    task_count          = 1
    task_definition_arn = aws_ecs_task_definition.misa_task[0].arn
    launch_type         = "FARGATE"
    platform_version    = "1.4.0"

    network_configuration {
      subnets          = local.ecs_subnet_ids
      security_groups  = [aws_security_group.misa_task_sg[0].id]
      assign_public_ip = true
    }
  }
}

resource "aws_s3_bucket_notification" "misa_backup_notification" {
  count       = var.misa_enabled ? 1 : 0
  bucket      = var.db_backup_bucket
  eventbridge = true
}

# -----------------------------------------------------------------------------
# SNS Topic & Alarms on Import Failures
# -----------------------------------------------------------------------------

resource "aws_sns_topic" "misa_alerts" {
  count = var.misa_enabled ? 1 : 0
  name  = "${var.project_name}-misa-alerts"
  tags  = local.common_tags
}

resource "aws_sns_topic_subscription" "misa_alerts_email" {
  count     = var.misa_enabled && var.misa_alarm_email != null ? 1 : 0
  topic_arn = aws_sns_topic.misa_alerts[0].arn
  protocol  = "email"
  endpoint  = var.misa_alarm_email
}

resource "aws_cloudwatch_log_metric_filter" "misa_import_failures" {
  count          = var.misa_enabled ? 1 : 0
  name           = "${var.project_name}-misa-import-failures"
  log_group_name = aws_cloudwatch_log_group.misa_logs.name
  pattern        = "\"[failed]\""

  metric_transformation {
    name          = "${var.project_name}-misa-import-failures"
    namespace     = "${var.project_name}/misa"
    value         = "1"
    default_value = "0"
  }
}

locals {
  misa_alarm_action_arn = var.misa_alarm_sns_topic_arn != null ? var.misa_alarm_sns_topic_arn : (var.misa_enabled ? aws_sns_topic.misa_alerts[0].arn : null)
}

resource "aws_cloudwatch_metric_alarm" "misa_import_failed_alarm" {
  count               = var.misa_enabled ? 1 : 0
  alarm_name          = "${var.project_name}-misa-import-failed"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = aws_cloudwatch_log_metric_filter.misa_import_failures[0].metric_transformation[0].name
  namespace           = aws_cloudwatch_log_metric_filter.misa_import_failures[0].metric_transformation[0].namespace
  period              = 300
  statistic           = "Sum"
  threshold           = 0
  alarm_description   = "Triggered when the MISA import runner encounters and logs one or more [failed] transactions"
  treat_missing_data  = "notBreaching"

  alarm_actions = local.misa_alarm_action_arn != null ? [local.misa_alarm_action_arn] : []
  ok_actions    = local.misa_alarm_action_arn != null ? [local.misa_alarm_action_arn] : []

  tags = local.common_tags
}

