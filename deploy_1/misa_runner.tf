# MISA Import Runner EC2 instance and trigger.
# See ai/update_misa_implementation/misa_deployment_design.md for the full design.

# -----------------------------------------------------------------------------
# AMI lookup
# -----------------------------------------------------------------------------

# Amazon Linux 2023 AMI if the caller does not supply a specific AMI.
data "aws_ami" "amazon_linux_2023" {
  count       = var.misa_enabled && var.misa_ami_id == null ? 1 : 0
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["al2023-ami-*-x86_64"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

locals {
  misa_ami_id = var.misa_enabled ? (var.misa_ami_id != null ? var.misa_ami_id : data.aws_ami.amazon_linux_2023[0].id) : null
}

# -----------------------------------------------------------------------------
# SSM Parameter Store (Free tier)
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

# Values are populated manually outside Terraform so they do not end up in
# Terraform state. The parameter names are passed to the EC2 user-data script.

# -----------------------------------------------------------------------------
# IAM
# -----------------------------------------------------------------------------

resource "aws_iam_role" "misa_runner_role" {
  count = var.misa_enabled ? 1 : 0
  name  = "${var.project_name}-misa-runner-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ec2.amazonaws.com"
        }
      }
    ]
  })

  tags = local.common_tags
}

resource "aws_iam_role_policy" "misa_runner_policy" {
  count = var.misa_enabled ? 1 : 0
  name  = "${var.project_name}-misa-runner-policy"
  role  = aws_iam_role.misa_runner_role[0].id

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
        Sid    = "EC2SelfTerminate"
        Effect = "Allow"
        Action = [
          "ec2:TerminateInstances",
          "ec2:StopInstances"
        ]
        Resource = "arn:aws:ec2:*:*:instance/*"
        Condition = {
          StringEquals = {
            "aws:ResourceTag/Project" = var.project_name
          }
        }
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
      },
      {
        Sid    = "ECRPull"
        Effect = "Allow"
        Action = [
          "ecr:GetAuthorizationToken",
          "ecr:BatchCheckLayerAvailability",
          "ecr:GetDownloadUrlForLayer",
          "ecr:BatchGetImage"
        ]
        Resource = "*"
      },
      {
        Sid    = "CloudWatchLogs"
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "${aws_cloudwatch_log_group.misa_logs.arn}:*"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "misa_runner_ssm" {
  count      = var.misa_enabled ? 1 : 0
  role       = aws_iam_role.misa_runner_role[0].name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_instance_profile" "misa_runner_profile" {
  count = var.misa_enabled ? 1 : 0
  name  = "${var.project_name}-misa-runner-profile"
  role  = aws_iam_role.misa_runner_role[0].name
  tags  = local.common_tags
}

# -----------------------------------------------------------------------------
# Security group
# -----------------------------------------------------------------------------

resource "aws_security_group" "misa_runner_sg" {
  count       = var.misa_enabled ? 1 : 0
  name        = "${var.project_name}-misa-runner-sg"
  description = "Security group for the MISA import runner EC2 instance"
  vpc_id      = var.vpc_id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(local.common_tags, {
    Name = "${var.project_name}-misa-runner-sg"
  })
}

# -----------------------------------------------------------------------------
# CloudWatch log group
# -----------------------------------------------------------------------------

resource "aws_cloudwatch_log_group" "misa_logs" {
  name              = "/ecs/${var.project_name}-misa"
  retention_in_days = 14
  tags              = local.common_tags
}

# Always create the log group so outputs are stable even when misa_enabled=false.

# -----------------------------------------------------------------------------
# EC2 Launch Template (Ephemeral On-Demand Runner)
# -----------------------------------------------------------------------------

locals {
  misa_runner_user_data = var.misa_enabled ? templatefile("${path.module}/files/misa_runner_user_data.sh", {
    region              = var.aws_region
    bucket              = var.db_backup_bucket
    db_key              = var.db_backup_key
    image               = "${aws_ecr_repository.app.repository_url}:${var.app_image_tag}"
    username_param_name = aws_ssm_parameter.misa_username[0].name
    password_param_name = aws_ssm_parameter.misa_password[0].name
    log_group           = aws_cloudwatch_log_group.misa_logs.name
  }) : ""
}

resource "aws_launch_template" "misa_runner" {
  count       = var.misa_enabled ? 1 : 0
  name_prefix = "${var.project_name}-misa-runner-"
  description = "Launch template for on-demand ephemeral MISA import runner"

  image_id      = local.misa_ami_id
  instance_type = var.misa_instance_type
  key_name      = var.misa_key_name

  iam_instance_profile {
    name = aws_iam_instance_profile.misa_runner_profile[0].name
  }

  network_interfaces {
    associate_public_ip_address = true
    subnet_id                   = var.misa_subnet_id
    security_groups             = [aws_security_group.misa_runner_sg[0].id]
  }

  user_data = base64encode(local.misa_runner_user_data)

  instance_initiated_shutdown_behavior = "terminate"

  block_device_mappings {
    device_name = "/dev/xvda"

    ebs {
      volume_size           = var.misa_root_volume_size
      volume_type           = "gp3"
      encrypted             = true
      delete_on_termination = true
    }
  }

  tag_specifications {
    resource_type = "instance"
    tags = merge(local.common_tags, {
      Name    = "${var.project_name}-misa-runner"
      Project = var.project_name
    })
  }

  tag_specifications {
    resource_type = "volume"
    tags = merge(local.common_tags, {
      Name    = "${var.project_name}-misa-runner-disk"
      Project = var.project_name
    })
  }

  tags = local.common_tags
}

# -----------------------------------------------------------------------------
# EventBridge: S3 PutObject -> start EC2 instance
# -----------------------------------------------------------------------------

resource "aws_cloudwatch_event_rule" "misa_db_backup_arrived" {
  count       = var.misa_enabled ? 1 : 0
  name        = "${var.project_name}-misa-db-backup-arrived"
  description = "Start the MISA import runner when txdb.sqlite3 is backed up to S3"

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

# Because EventBridge cannot directly start an EC2 instance via a built-in
# target, use a tiny Lambda function as the target.

resource "aws_iam_role" "eventbridge_ec2_start_role" {
  count = var.misa_enabled ? 1 : 0
  name  = "${var.project_name}-eventbridge-ec2-start-role"

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

resource "aws_iam_role_policy" "eventbridge_ec2_start_policy" {
  count = var.misa_enabled ? 1 : 0
  name  = "${var.project_name}-eventbridge-ec2-start-policy"
  role  = aws_iam_role.eventbridge_ec2_start_role[0].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["lambda:InvokeFunction"]
        Resource = [aws_lambda_function.misa_start_runner[0].arn]
      }
    ]
  })
}

resource "aws_iam_role" "misa_start_runner_lambda_role" {
  count = var.misa_enabled ? 1 : 0
  name  = "${var.project_name}-misa-start-runner-lambda-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })

  tags = local.common_tags
}

resource "aws_iam_role_policy" "misa_start_runner_lambda_policy" {
  count = var.misa_enabled ? 1 : 0
  name  = "${var.project_name}-misa-start-runner-lambda-policy"
  role  = aws_iam_role.misa_start_runner_lambda_role[0].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "ec2:RunInstances",
          "ec2:DescribeInstances",
          "ec2:CreateTags"
        ]
        Resource = "*"
      },
      {
        Effect   = "Allow"
        Action   = ["iam:PassRole"]
        Resource = [aws_iam_role.misa_runner_role[0].arn]
      },
      {
        Effect   = "Allow"
        Action   = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "arn:aws:logs:*:*:*"
      }
    ]
  })
}

resource "archive_file" "misa_start_runner_lambda" {
  count       = var.misa_enabled ? 1 : 0
  type        = "zip"
  output_path = "${path.module}/.terraform/misa_start_runner_lambda.zip"

  source {
    content  = <<-EOF
      import json
      import boto3
      import os

      REGION = os.environ["REGION"]
      LAUNCH_TEMPLATE_ID = os.environ["LAUNCH_TEMPLATE_ID"]
      PROJECT_NAME = os.environ.get("PROJECT_NAME", "spendsense")

      def handler(event, context):
          ec2 = boto3.client("ec2", region_name=REGION)
          existing = ec2.describe_instances(
              Filters=[
                  {"Name": "tag:Project", "Values": [PROJECT_NAME]},
                  {"Name": "instance-state-name", "Values": ["pending", "running"]},
              ]
          )
          running_ids = [
              i["InstanceId"]
              for r in existing.get("Reservations", [])
              for i in r.get("Instances", [])
          ]
          if running_ids:
              print(f"MISA runner already active: {running_ids}")
              return {"statusCode": 200, "body": json.dumps({"already_running": running_ids})}

          response = ec2.run_instances(
              LaunchTemplate={"LaunchTemplateId": LAUNCH_TEMPLATE_ID, "Version": "$Latest"},
              MinCount=1,
              MaxCount=1,
          )
          instance_id = response["Instances"][0]["InstanceId"]
          print(f"Launched ephemeral MISA runner instance: {instance_id}")
          return {"statusCode": 200, "body": json.dumps({"launched": instance_id})}
    EOF
    filename = "index.py"
  }
}

resource "aws_lambda_function" "misa_start_runner" {
  count         = var.misa_enabled ? 1 : 0
  function_name = "${var.project_name}-misa-start-runner"
  role          = aws_iam_role.misa_start_runner_lambda_role[0].arn
  handler       = "index.handler"
  runtime       = "python3.13"
  filename      = archive_file.misa_start_runner_lambda[0].output_path
  timeout       = 30

  environment {
    variables = {
      REGION             = var.aws_region
      LAUNCH_TEMPLATE_ID = aws_launch_template.misa_runner[0].id
      PROJECT_NAME       = var.project_name
    }
  }

  source_code_hash = archive_file.misa_start_runner_lambda[0].output_base64sha256

  tags = local.common_tags
}

resource "aws_cloudwatch_event_target" "misa_start_runner_lambda" {
  count = var.misa_enabled ? 1 : 0
  rule  = aws_cloudwatch_event_rule.misa_db_backup_arrived[0].name
  arn   = aws_lambda_function.misa_start_runner[0].arn
}

resource "aws_lambda_permission" "allow_eventbridge" {
  count         = var.misa_enabled ? 1 : 0
  statement_id  = "AllowExecutionFromEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.misa_start_runner[0].function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.misa_db_backup_arrived[0].arn
}

# S3 event notification to EventBridge must be enabled on the bucket.
# NOTE: aws_s3_bucket_notification replaces all notifications on the bucket.
# If other notifications are added later, centralize them in one resource.
resource "aws_s3_bucket_notification" "misa_backup_notification" {
  count       = var.misa_enabled ? 1 : 0
  bucket      = var.db_backup_bucket
  eventbridge = true
}

# -----------------------------------------------------------------------------
# Safety stop: EventBridge schedule -> Lambda stop EC2 instance
# -----------------------------------------------------------------------------

resource "aws_iam_role" "misa_stop_runner_lambda_role" {
  count = var.misa_enabled ? 1 : 0
  name  = "${var.project_name}-misa-stop-runner-lambda-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })

  tags = local.common_tags
}

resource "aws_iam_role_policy" "misa_stop_runner_lambda_policy" {
  count = var.misa_enabled ? 1 : 0
  name  = "${var.project_name}-misa-stop-runner-lambda-policy"
  role  = aws_iam_role.misa_stop_runner_lambda_role[0].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "ec2:DescribeInstances",
          "ec2:TerminateInstances",
          "ec2:StopInstances"
        ]
        Resource = "*"
      },
      {
        Effect   = "Allow"
        Action   = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "arn:aws:logs:*:*:*"
      }
    ]
  })
}

resource "archive_file" "misa_stop_runner_lambda" {
  count       = var.misa_enabled ? 1 : 0
  type        = "zip"
  output_path = "${path.module}/.terraform/misa_stop_runner_lambda.zip"

  source {
    content  = <<-EOF
      import json
      import boto3
      import os

      REGION = os.environ["REGION"]
      PROJECT_NAME = os.environ.get("PROJECT_NAME", "spendsense")

      def handler(event, context):
          ec2 = boto3.client("ec2", region_name=REGION)
          existing = ec2.describe_instances(
              Filters=[
                  {"Name": "tag:Project", "Values": [PROJECT_NAME]},
                  {"Name": "instance-state-name", "Values": ["pending", "running"]},
              ]
          )
          instance_ids = [
              i["InstanceId"]
              for r in existing.get("Reservations", [])
              for i in r.get("Instances", [])
          ]
          if instance_ids:
              ec2.terminate_instances(InstanceIds=instance_ids)
              print(f"Safety terminated instances: {instance_ids}")
          return {
              "statusCode": 200,
              "body": json.dumps({"terminated": instance_ids})
          }
    EOF
    filename = "index.py"
  }
}

resource "aws_lambda_function" "misa_stop_runner" {
  count         = var.misa_enabled ? 1 : 0
  function_name = "${var.project_name}-misa-stop-runner"
  role          = aws_iam_role.misa_stop_runner_lambda_role[0].arn
  handler       = "index.handler"
  runtime       = "python3.13"
  filename      = archive_file.misa_stop_runner_lambda[0].output_path
  timeout       = 30

  environment {
    variables = {
      REGION       = var.aws_region
      PROJECT_NAME = var.project_name
    }
  }

  source_code_hash = archive_file.misa_stop_runner_lambda[0].output_base64sha256

  tags = local.common_tags
}

resource "aws_cloudwatch_event_rule" "misa_safety_stop" {
  count               = var.misa_enabled ? 1 : 0
  name                = "${var.project_name}-misa-safety-stop"
  description         = "Forcefully stops the MISA EC2 runner if it has not stopped itself within the execution window"
  schedule_expression = var.misa_safety_stop_schedule

  tags = local.common_tags
}

resource "aws_cloudwatch_event_target" "misa_safety_stop_lambda" {
  count = var.misa_enabled ? 1 : 0
  rule  = aws_cloudwatch_event_rule.misa_safety_stop[0].name
  arn   = aws_lambda_function.misa_stop_runner[0].arn
}

resource "aws_lambda_permission" "allow_eventbridge_safety_stop" {
  count         = var.misa_enabled ? 1 : 0
  statement_id  = "AllowExecutionFromEventBridgeSafetyStop"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.misa_stop_runner[0].function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.misa_safety_stop[0].arn
}

# -----------------------------------------------------------------------------
# SNS Topic & Notifications
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

# -----------------------------------------------------------------------------
# CloudWatch Metric Filter & Alarm on Import Failures
# -----------------------------------------------------------------------------

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
