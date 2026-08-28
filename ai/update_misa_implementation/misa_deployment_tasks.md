# Task: Deploy the MISA Import Runner on AWS (ECS Fargate)

> Tracks implementation of [misa_deployment_design.md](./misa_deployment_design.md).
> Checkboxes: `[ ]` not started, `[x]` done.

## 1. Objective

Add AWS infrastructure and CI/CD changes so that the MISA import runner starts
automatically as an on-demand **AWS ECS Fargate Task** after the daily SQLite backup lands in S3,
imports pending Spend/Earn transactions, uploads the updated database back to S3,
and terminates with direct real-time logs in CloudWatch.

## 2. Blocking Prerequisites

Resolve these before production deployment:

1. [x] `app/misa/runner.py` exists and supports `--start-date` / `--end-date`.
2. [x] `misa_import_state` table is implemented and `DedupStore` uses it.
3. [x] `app/misa/client.py::add_transaction()` uses the Save-and-close button
   and handles both Spend and Earn tabs.
4. [x] Dockerfile supports `APP_ROLE=misa` and contains Playwright Chromium.
5. [x] MISA credentials are stored in AWS SSM Parameter Store (`/spendsense/misa_username` and `/spendsense/misa_password` as `SecureString`).
6. [x] Backup bucket and ECR repository exist (already created by `deploy_1/main.tf`).

## 3. Required Tasks

### 3.1 Docker image
1. [x] Update [Dockerfile](../../Dockerfile) with `boto3` and Playwright Chromium for fast Fargate execution:
   ```dockerfile
   RUN pip install --no-cache-dir playwright==1.62.0 && playwright install --with-deps chromium
   ```
2. [x] Confirm `boto3` is present in `requirements.txt` for SSM/S3 integration.
3. [x] Extend `app/misa/runner.py` to resolve credentials from SSM Parameter Store via `MISA_USERNAME_PARAM_NAME` / `MISA_PASSWORD_PARAM_NAME`.
4. [x] Add unit tests for SSM parameter resolution (`tests/test_misa_runner.py`).

### 3.2 ECS Fargate Task Definition
1. [ ] Create `aws_ecs_task_definition.misa_task` (`spendsense-misa-task`) in `deploy_1/misa_runner.tf`:
   - 1024 CPU, 2048 MB Memory.
   - `awsvpc` network mode, `FARGATE` compatibility.
   - Environment variables for S3 bucket, key, and SSM parameter names.
   - `awslogs` log driver streaming directly to `/ecs/spendsense-misa`.
2. [ ] Define `aws_iam_role.misa_task_execution_role` and `aws_iam_role.misa_task_role`.
3. [ ] Define `aws_security_group.misa_task_sg` with egress-only rule.
4. [ ] Deprecate old EC2 resources (instance profile, launch templates, Lambda proxy scripts).

### 3.3 EventBridge Trigger (Native ECS Target)
1. [ ] Ensure S3 PutObject events on `txdb.sqlite3` are captured by EventBridge rule `spendsense-misa-db-backup-arrived`.
2. [ ] Configure `aws_cloudwatch_event_target.misa_task` using native `ecs_target` calling `ecs:RunTask` on `spendsense-cluster`.
3. [ ] Configure IAM role allowing EventBridge to invoke `ecs:RunTask` with `iam:PassRole`.

### 3.4 SSM Parameter Store
1. [x] Manage `aws_ssm_parameter.misa_username` and `aws_ssm_parameter.misa_password` with `lifecycle { ignore_changes = [value] }`.
2. [x] Populate secret values via AWS CLI or SSM Console.

### 3.5 CloudWatch Logging & Alarms
1. [x] Create `aws_cloudwatch_log_group.misa_logs` (`/ecs/spendsense-misa`) with 14-day retention.
2. [x] Create `aws_cloudwatch_log_metric_filter.misa_import_failures` for `"[failed]"` log entries.
3. [x] Create CloudWatch alarm `aws_cloudwatch_metric_alarm.misa_import_failed_alarm` connected to SNS.

### 3.6 CI/CD Pipeline
1. [x] Auto-import SSM parameters in `.github/workflows/cicd.yml`.
2. [ ] Build and push single Docker image containing Playwright to ECR.

## 4. Acceptance Criteria

- [x] `python -m app.misa.runner --dry-run` works locally with 100% test coverage.
- [ ] EventBridge automatically invokes the Fargate MISA task when `txdb.sqlite3` lands in S3.
- [ ] Fargate task starts in seconds, imports pending transactions, and uploads the updated DB back to S3.
- [ ] Real-time container logs are visible directly in CloudWatch `/ecs/spendsense-misa`.
- [ ] Task self-terminates upon completion with zero lingering EBS storage costs ($0.00/month).
- [ ] Failed transactions trigger SNS alarm notifications.

## 5. Status Summary

| Component | Status | Notes |
| :--- | :--- | :--- |
| **MISA Client & Mapper** | Done | Verified with MISA Web UI |
| **SSM Parameter Store** | Done | Free Tier SecureString |
| **Docker & Dependencies** | Done | `boto3` & Playwright included |
| **ECS Fargate Architecture** | Specified | Documentation updated |
| **Terraform ECS Migration** | Next Step | Implement `aws_ecs_task_definition.misa_task` |

