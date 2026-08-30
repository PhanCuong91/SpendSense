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

resource "aws_security_group_rule" "efs_ingress_misa_task" {
  count                    = var.misa_enabled ? 1 : 0
  type                     = "ingress"
  from_port                = 2049
  to_port                  = 2049
  protocol                 = "tcp"
  security_group_id        = aws_security_group.efs_sg.id
  source_security_group_id = aws_security_group.misa_task_sg[0].id
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
      name      = "${var.project_name}-misa"
      image     = local.app_image_url
      essential = true

      environment = [
        {
          name  = "PYTHONPATH"
          value = "/app"
        },
        {
          name  = "DATABASE_URL"
          value = var.db_file_path
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
          name  = "AWS_REGION"
          value = var.aws_region
        }
      ]

      mountPoints = [
        {
          sourceVolume  = "efs-data"
          containerPath = var.db_mount_path
          readOnly      = false
        }
      ]

      command = [
        "/bin/sh",
        "-c",
        <<-EOT
          set -e
          echo "=== [1/2] Running MISA Import from EFS Database ==="
          START_DATE=$(date -d 'yesterday' +%Y-%m-%d)
          END_DATE=$(date +%Y-%m-%d)
          python -m app.misa.runner --start-date "$START_DATE" --end-date "$END_DATE"
          echo "=== [2/2] MISA Task Finished Successfully ==="
        EOT
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
# EventBridge: app_task STOPPED -> Run MISA Fargate Task
# -----------------------------------------------------------------------------

resource "aws_cloudwatch_event_target" "run_misa_task" {
  count     = var.misa_enabled ? 1 : 0
  target_id = "${var.project_name}-misa-task-target"
  arn       = aws_ecs_cluster.app_cluster.arn
  rule      = aws_cloudwatch_event_rule.app_task_stopped.name
  role_arn  = aws_iam_role.eventbridge_ecs_role.arn

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

# -----------------------------------------------------------------------------
# EventBridge: misa_task STOPPED -> Run Backup Fargate Task
# -----------------------------------------------------------------------------

resource "aws_cloudwatch_event_rule" "misa_task_stopped" {
  count       = var.misa_enabled ? 1 : 0
  name        = "${var.project_name}-misa-task-stopped"
  description = "Run the database backup task after the MISA import task has stopped"

  event_pattern = jsonencode({
    source      = ["aws.ecs"]
    detail-type = ["ECS Task State Change"]
    detail = {
      lastStatus        = ["STOPPED"]
      desiredStatus     = ["STOPPED"]
      clusterArn        = [aws_ecs_cluster.app_cluster.arn]
      taskDefinitionArn = [aws_ecs_task_definition.misa_task[0].arn]
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

resource "aws_cloudwatch_event_target" "run_backup_task_after_misa" {
  count               = var.misa_enabled ? 1 : 0
  target_id           = "${var.project_name}-backup-task-after-misa-target"
  arn                 = aws_ecs_cluster.app_cluster.arn
  rule                = aws_cloudwatch_event_rule.misa_task_stopped[0].name
  role_arn            = aws_iam_role.eventbridge_misa_ecs_role[0].arn

  ecs_target {
    task_count          = 1
    task_definition_arn = aws_ecs_task_definition.backup_task.arn
    launch_type         = "FARGATE"
    platform_version    = "1.4.0"

    network_configuration {
      subnets          = local.ecs_subnet_ids
      security_groups  = [aws_security_group.ecs_sg.id]
      assign_public_ip = true
    }
  }
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

