# Task: Deploy the MISA Import Runner on AWS

> Tracks implementation of [misa_deployment_design.md](./misa_deployment_design.md).
> Checkboxes: `[ ]` not started, `[x]` done.

## 1. Objective

Add AWS infrastructure and CI/CD changes so that the MISA import runner starts
automatically after the daily SQLite backup lands in S3, imports yesterday's
and today's Spend/Earn transactions, uploads the updated database back to S3,
and then stops itself.

## 2. Blocking Prerequisites

Resolve these before production deployment:

1. [x] `app/misa/runner.py` exists and supports `--start-date` / `--end-date`.
2. [x] `misa_import_state` table is implemented and `DedupStore` uses it.
3. [x] `app/misa/client.py::add_transaction()` uses the Save-and-close button
   and handles both Spend and Earn tabs (resolved 2026-08-08 per
   `/memories/repo/misa_selectors.md`).
4. [x] Dockerfile supports `APP_ROLE=misa`.
5. [ ] MISA credentials are stored in AWS Secrets Manager (Terraform creates
   the secrets; values must be populated manually outside Terraform).
6. [x] Backup bucket and ECR repository exist (already created by existing
   `deploy_1/main.tf`).

## 3. Required Tasks

### 3.1 Docker image

Required actions:

1. [x] Update [Dockerfile](../../Dockerfile) `CMD` to add the `misa` role:
   ```dockerfile
   misa) exec python -m app.misa.runner ;;
   ```
   Do **not** install Playwright browsers in the image.
2. [x] Confirm `awscli` is installed in the image (already present) so the EC2
   user-data script can use it for S3/Secrets Manager.
3. [x] Extend `app/misa/runner.py` to resolve credentials from Secrets Manager
   when `MISA_USERNAME_SECRET_ARN` / `MISA_PASSWORD_SECRET_ARN` are set,
   falling back to plain `MISA_USERNAME` / `MISA_PASSWORD` for local dev.
4. [x] Add a unit test for the Secrets Manager resolution path (mock
   `boto3.client("secretsmanager")`).
5. [x] Make `runner.py` and `client.py` import Playwright lazily so the image
   does not need `playwright` installed and `APP_ROLE=misa --dry-run` works.
6. [x] Build linux image in MacOS docker and push a new image with the `misa` role to ECR.

### 3.2 EC2 runner instance

Required actions:

1. [x] Choose AMI: Amazon Linux 2023 with Docker and `awscli` pre-installed,
   or use a standard AL2023 AMI and install Docker in user-data (AMI lookup
   data source added; Docker install included in user-data as a fallback).
2. [x] Create `deploy_1/misa_runner.tf` with:
   - `aws_instance.misa_runner` (`t3.micro`, public subnet, instance profile,
     security group, user-data).
   - `aws_iam_role.misa_runner_role`.
   - `aws_iam_instance_profile.misa_runner_profile`.
   - `aws_iam_role_policy.misa_runner_policy` granting S3, ECR, Secrets
     Manager, EC2 stop-instances, CloudWatch Logs, and optional SSM.
   - `aws_security_group.misa_runner_sg` with egress-only rule.
3. [x] Create `deploy_1/files/misa_runner_user_data.sh` containing the script
   from misa_deployment_design.md §4.2, templated with Terraform variables.
4. [x] Add variables to [deploy_1/variables.tf](../../deploy_1/variables.tf):
   `misa_enabled`, `misa_ami_id`, `misa_instance_type`, `misa_subnet_id`,
   `misa_key_name`, `misa_root_volume_size`.
5. [x] Add outputs to [deploy_1/outputs.tf](../../deploy_1/outputs.tf) for
   `misa_runner_instance_id`, `misa_runner_security_group_id`,
   `misa_log_group_name`, `misa_username_secret_arn`, and
   `misa_password_secret_arn`.
6. [ ] Run `terraform plan` and `terraform apply` in `deploy_1/`.

### 3.3 EventBridge trigger

Required actions:

1. [x] Add `aws_s3_bucket_notification` on the backup bucket to send
   `s3:ObjectCreated:PutObject` events to EventBridge for `txdb.sqlite3`.
2. [x] Create `aws_cloudwatch_event_rule.misa_db_backup_arrived` matching S3
   `Object Created` events for the configured bucket and key.
3. [x] Create an EventBridge target that starts the MISA runner instance via a
   small Lambda proxy (`aws_lambda_function.misa_start_runner`), because
   EventBridge has no first-class EC2 `StartInstances` target.
4. [x] Grant EventBridge permission to invoke the Lambda via an IAM role and
   `aws_lambda_permission`.

### 3.4 Secrets Manager

Required actions:

1. [x] Add `aws_secretsmanager_secret.misa_username` and
   `aws_secretsmanager_secret.misa_password` to Terraform.
2. [ ] Set secret values manually via AWS Console or CLI; do **not** commit
   them to Terraform state or the repository.
3. [x] Pass the secret ARNs into the EC2 user-data template.
4. [x] Add a unit test proving `runner.py` falls back to Secrets Manager ARNs
   when `MISA_USERNAME`/`MISA_PASSWORD` are not set.

### 3.5 CloudWatch logging

Required actions:

1. [x] Create `aws_cloudwatch_log_group.misa_logs` (`/ecs/spendsense-misa`)
   with 14-day retention.
2. [x] Confirm the EC2 instance profile allows `logs:CreateLogStream` and
   `logs:PutLogEvents` for that log group ARN.
3. [x] Verify the log group accepts events (manual `boto3` test created the
   `manual-test-boto` stream and wrote a test event). The Docker Desktop
   `awslogs` driver could not be fully exercised locally because it insists on
   sourcing credentials from EC2 IMDS/ECS endpoints rather than environment
   variables, but the IAM instance profile grants the required permissions and
   the log group itself is confirmed working.

### 3.6 Safety and monitoring

Required actions:

1. [x] Add an EventBridge schedule that stops the MISA runner instance if it
   has been running for more than 10 minutes (implemented via safety stop Lambda
   and EventBridge cron rule).
2. [x] Add a CloudWatch log metric filter for `[failed]` lines and an alarm.
3. [x] Optional: create an SNS topic and email subscription for the alarm.
4. [x] Add a `terraform.tfvars.example` note documenting the new MISA
   variables.

### 3.7 CI/CD integration

Required actions:

1. [ ] Update `.github/workflows/cicd.yml` (or `cd.yml` if split) to pass the
   `misa` image tag to Terraform, using the same tag as the app image.
2. [ ] Ensure the CI pipeline builds the image once and reuses it for both ECS
   and EC2 MISA runner.
3. [ ] Add a post-deploy smoke test that checks the MISA runner instance exists
   and is in `stopped` state after Terraform apply.

### 3.8 End-to-end verification

Required actions:

1. [ ] Manually trigger the S3 event (or start the EC2 instance) and watch the
   import run.
2. [ ] Confirm:
   - DB is downloaded from S3.
   - Playwright Chromium installs.
   - MISA login succeeds.
   - Transactions are imported (check MISA UI).
   - Updated DB is uploaded to S3.
   - Instance stops.
3. [ ] Verify re-running does not duplicate already-imported rows.
4. [ ] Update this task doc with the date of successful verification.

## 4. Acceptance Criteria

- [x] `docker run -e APP_ROLE=misa ... python -m app.misa.runner --dry-run`
      works locally against a copy of `txdb.sqlite3`.
- [ ] Terraform creates the EC2 instance, IAM role, security group, EventBridge
      rule, and CloudWatch log group without error.
- [ ] Uploading `txdb.sqlite3` to the backup bucket starts the EC2 instance.
- [ ] The EC2 instance imports transactions, uploads the updated DB, and stops.
- [ ] Re-running the pipeline does not re-import previously successful rows.
- [ ] No MISA credentials appear in the repository, Terraform state, or logs.

## 5. Status Summary

| Phase | Status |
|---|---|
| MISA automation implementation | Done (2026-08-08) |
| Docker image `APP_ROLE=misa` | Done |
| `runner.py` Secrets Manager resolution | Done |
| Lazy Playwright imports | Done |
| Linux image built and pushed to ECR | Done (tag: `misa-7df5622`) |
| EC2 runner Terraform | Done (applied; instance `i-01104b23bac8a8fc3`) |
| EventBridge S3 trigger | Done (applied) |
| Secrets Manager credentials | Created by Terraform; values not yet populated |
| CloudWatch log group | Done |
| Safety/alarms | Done |
| CI/CD integration | Not started |
| End-to-end verification | Not started |

## 6. Notes

- `deploy_1/misa_runner.tf` creates `aws_secretsmanager_secret` resources for
  `misa_username` and `misa_password`, but intentionally does **not** set their
  values. This keeps real credentials out of Terraform state and the repo.
- After `terraform apply`, set the secret values via AWS CLI:
  ```bash
  aws secretsmanager put-secret-value \
    --secret-id spendsense_misa_username \
    --secret-string "YOUR_MISA_USERNAME"

  aws secretsmanager put-secret-value \
    --secret-id spendsense_misa_password \
    --secret-string "YOUR_MISA_PASSWORD"
  ```
- The EC2 user-data script passes the secret ARNs via
  `MISA_USERNAME_SECRET_ARN` and `MISA_PASSWORD_SECRET_ARN` environment
  variables, and `app/misa/runner.py` resolves them at runtime.
