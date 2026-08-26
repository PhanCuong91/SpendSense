# AWS Deployment Recommendations

> Based on review of:
> - `.github/workflows/cicd.yml`
> - `.github/workflows/python-test.yml`
> - `.github/workflows/remove-label.yml`
> - `deploy_1/main.tf`
> - `deploy_1/variables.tf`
> - `deploy_1/outputs.tf`
> - `deploy_1/backend.tf`
> - `Dockerfile`
> - `docker-compose.yaml`

---

## 1. Executive Summary

The current pipeline **deploys successfully** but has several design, security, and operational gaps. The biggest issues are:

1. **The deployed container runs the wrong command**: `deploy_1/main.tf` launches `python -m app.workers.poller_worker --host 0.0.0.0 --port 8000`, but the poller worker does not accept host/port args. There is no API container.
2. **AWS authentication uses long-term credentials** despite OIDC being partially configured.
3. **CI/CD is label-driven and auto-merges on label**, which is risky and non-standard.
4. **Only a subset of tests runs in CI** (`test_gmail_polling.py` + `test_parser.py`), so regressions in correlator/event-builder/MISA can slip through.
5. **SQLite on EFS with a single task** is acceptable for low-volume personal use, but the current task definition does not include the correlator worker or the API.

This document proposes a safer, more maintainable deployment approach.

---

## 2. Critical Issues in Current Setup

### 2.1 CICD Pipeline (`cicd.yml`)

| Issue | Severity | Explanation |
|-------|----------|-------------|
| **Long-term AWS credentials** | High | Uses `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY`. Should use OIDC (`configure-aws-credentials` with `role-to-assume`). |
| **Wrong `PYTHONPATH`** in merge job | High | Sets `PYTHONPATH: src`, but the codebase uses `app.*` imports at repo root. Tests will fail or import the wrong module. |
| **Auto-merge on label** | High | Anyone who can add a label can force a merge. Standard practice: require PR reviews + status checks. |
| **CD depends on merge-label job** | High | CD runs from the PR before the merge actually lands on `main`. The SHA used is the PR head, not the merge commit. |
| **Short image tag (5-char SHA)** | Medium | Collision-prone and hard to trace. Use full SHA or semver. |
| **Only 2 test files run** | Medium | `test_correlator.py`, `test_event_builder.py`, `test_misa_*.py`, etc. are skipped in CI. |
| **No post-deploy verification** | Medium | After `terraform apply`, nothing checks that the service is healthy. |
| **No deployment environment/approval** | Medium | Direct apply to production from PR merge with no gate. |
| **Cleanup job may fail** | Low | `remove-label.yml` uses `github.event.label.name`; on `workflow_dispatch` this is empty. |
| **Duplicate Terraform plan/apply pattern** | Low | Uses `terraform plan -out=tfplan` then `terraform apply tfplan` correctly, which is good. |

### 2.2 Terraform Infrastructure (`deploy_1/main.tf`)

| Issue | Severity | Explanation |
|-------|----------|-------------|
| **Single container, wrong command** | Critical | The task runs the poller worker with API flags. No API, no correlator. |
| **`db_file_path` default mismatch** | High | Default is `sqlite:///./data/txdb.sqlite3`, but EFS is mounted at `/app/data`. Should be `sqlite:///./data/txdb.sqlite3` with `db_mount_path = /app/data` — currently consistent by luck, but fragile. |
| **No container health check** | High | ECS service has no `healthCheck` in container definition; it only knows if the process exits. |
| **Public IP required** | Medium | `assign_public_ip = true` is needed because tasks must reach ECR, Secrets Manager, and Gmail. Acceptable for personal project; for production, add NAT Gateway + VPC endpoints. |
| **EFS in public subnets** | Medium | Mount targets are placed in the same subnets as ECS tasks. Better to separate EFS into private subnets if you have them. |
| **Self-referential 443 ingress** | Low | The `ecs_allow_tls_self` rule allows ingress from the same SG on 443, but the app does not accept inbound HTTPS. Harmless but unnecessary. |
| **Backup image tag hardcoded** | Low | `backup_container_image_tag = "backup-efs-amd64"` is pushed manually. Should build/push in CI too. |
| **State lock handling** | Good | Lock timeout and error messaging for state lock are thoughtful. |
| **S3 backend with DynamoDB lock** | Good | Proper remote state setup. |

---

## 3. Recommended Better Approach

### 3.1 High-Level CICD Design

```
PR opened/updated
       │
       ▼
┌─────────────────┐
│  CI: Lint/Test  │  ← run full pytest suite
│  (no secrets)   │
└─────────────────┘
       │
       ▼
PR merged to main
       │
       ▼
┌─────────────────┐
│  Build & Push   │  ← build app + backup images, push to ECR
│  Tag: sha+semver│
└─────────────────┘
       │
       ▼
┌─────────────────┐
│  CD: Terraform  │  ← OIDC auth, plan, apply
│  (environment)  │
└─────────────────┘
       │
       ▼
┌─────────────────┐
│ Smoke Test      │  ← call /health, check ECS task running
└─────────────────┘
```

### 3.2 Infrastructure Design

**Option A: One ECS task with three containers (recommended for simplicity)**

One Fargate task containing:
- `api` → `uvicorn app.main:app --host 0.0.0.0 --port 8000`
- `poller` → `python -m app.workers.poller_worker`
- `correlator` → `python -m app.workers.correlator_worker`

All share the same EFS mount at `/app/data`.

Pros: single task, one EFS mount, simple Terraform.
Cons: if one container crashes, the whole task restarts; cannot scale API independently.

**Option B: Separate ECS services for each role**

- `spendsense-api` service (desired_count = 1, potentially behind ALB)
- `spendsense-poller` service (desired_count = 1)
- `spendsense-correlator` service (desired_count = 1)

Pros: independent lifecycle, can scale API separately later.
Cons: more Terraform, more cost if always-on.

For a personal project, **Option A is sufficient**.

### 3.3 Database Strategy

Keep SQLite on EFS for now, but add:
- **Backup before task stop** (already implemented via EventBridge + backup task).
- **Backup on schedule** (e.g. every 6 hours) in addition to stop-triggered backup.
- **Restore on startup** from S3 if DB missing (already implemented).

Long-term, consider **RDS PostgreSQL** if you want concurrent API containers or proper managed backups.

---

## 4. Concrete Recommendations

### 4.1 CICD Changes

#### A. Use OIDC instead of long-term AWS credentials

```yaml
- name: Configure AWS Credentials
  uses: aws-actions/configure-aws-credentials@v4
  with:
    role-to-assume: arn:aws:iam::<account>:role/GitHubActionsDeployRole
    aws-region: ap-southeast-1
```

Create an IAM role with:
- Trusted entity: `token.actions.githubusercontent.com`
- Condition: `StringEquals` for `repo:owner/repo` and (optionally) `ref:refs/heads/main`
- Permissions: ECR push/pull, ECS/ECR/Terraform state access.

Delete `secrets.AWS_ACCESS_KEY_ID` and `secrets.AWS_SECRET_ACCESS_KEY` validation.

#### B. Split into `ci.yml` and `cd.yml`

**`ci.yml`** — run on every PR:

```yaml
on:
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.13' }
      - run: pip install -r requirements.txt
      - run: pytest -q
```

> Note: do **not** set `PYTHONPATH: src`. The tests run from repo root and import `app.*` correctly.

**`cd.yml`** — run on push to `main`:

```yaml
on:
  push:
    branches: [main]

jobs:
  build:
    runs-on: ubuntu-latest
    permissions:
      id-token: write
      contents: read
    outputs:
      image_tag: ${{ steps.meta.outputs.tags }}
    steps:
      - uses: actions/checkout@v4
      - uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: ${{ secrets.AWS_DEPLOY_ROLE_ARN }}
          aws-region: ap-southeast-1
      - run: |
          aws ecr get-login-password | docker login --username AWS --password-stdin <account>.dkr.ecr.ap-southeast-1.amazonaws.com
          IMAGE_TAG=sha-${{ github.sha }}
          docker build -t spend_sense:${IMAGE_TAG} .
          docker tag spend_sense:${IMAGE_TAG} <account>.dkr.ecr.ap-southeast-1.amazonaws.com/spend_sense:${IMAGE_TAG}
          docker push <account>.dkr.ecr.ap-southeast-1.amazonaws.com/spend_sense:${IMAGE_TAG}
          echo "image_tag=${IMAGE_TAG}" >> $GITHUB_OUTPUT

  deploy:
    needs: build
    runs-on: ubuntu-latest
    environment: production
    permissions:
      id-token: write
      contents: read
    steps:
      - uses: actions/checkout@v4
      - uses: hashicorp/setup-terraform@v3
      - uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: ${{ secrets.AWS_DEPLOY_ROLE_ARN }}
          aws-region: ap-southeast-1
      - run: |
          cd deploy_1
          terraform init -input=false
          terraform plan -var="app_image_tag=${{ needs.build.outputs.image_tag }}" -out=tfplan
          terraform apply -auto-approve tfplan
```

#### C. Use GitHub Environments for deployment approval

Define a `production` environment in GitHub Settings → Environments. The `deploy` job then waits for manual approval before applying Terraform.

#### D. Add post-deploy smoke test

```yaml
- name: Smoke test
  run: |
    # Get task public IP or use AWS CLI to check service status
    aws ecs describe-services --cluster spendsense-cluster --services spendsense-service
    # If you add a public ALB later:
    # curl -sf https://<alb>/health || exit 1
```

#### E. Run the full test suite in CI

Replace the two-file subset with:

```yaml
- run: pytest -q
```

Gmail tests may need `GMAIL_TOKEN_JSON` and `GMAIL_CREDENTIALS_JSON` if they hit the real API. Consider mocking Gmail API calls so CI does not need real secrets.

### 4.2 Terraform Changes

#### A. Make the Dockerfile command role-aware

Update `Dockerfile`:

```dockerfile
CMD ["sh", "-c", "\
  case \"$APP_ROLE\" in \
    api) exec uvicorn app.main:app --host 0.0.0.0 --port 8000 ;; \
    poller) exec python -m app.workers.poller_worker ;; \
    correlator) exec python -m app.workers.correlator_worker ;; \
    *) echo \"Unknown APP_ROLE=$APP_ROLE\"; exit 1 ;; \
  esac"]
```

#### B. Change task definition to run three containers

Replace the single `app_task` container with three containers sharing the same EFS volume:

```hcl
container_definitions = jsonencode([
  {
    name  = "api",
    image = "${aws_ecr_repository.app.repository_url}:${var.app_image_tag}",
    essential = true,
    environment = [
      { name = "APP_ROLE", value = "api" },
      { name = "DATABASE_URL", value = var.db_file_path }
    ],
    secrets = [...],
    portMappings = [{ containerPort = 8000, protocol = "tcp" }],
    healthCheck = {
      command = ["CMD-SHELL", "python -c 'import urllib.request; urllib.request.urlopen(\"http://127.0.0.1:8000/health\", timeout=3)' >/dev/null 2>&1 || exit 1"]
      interval = 30
      timeout = 5
      retries = 5
      startPeriod = 15
    },
    mountPoints = [{ sourceVolume = "efs-data", containerPath = var.db_mount_path, readOnly = false }],
    logConfiguration = {...}
  },
  {
    name = "poller",
    image = "...",
    essential = false,
    environment = [
      { name = "APP_ROLE", value = "poller" },
      { name = "DATABASE_URL", value = var.db_file_path }
    ],
    secrets = [...],
    mountPoints = [...],
    logConfiguration = {...}
  },
  {
    name = "correlator",
    image = "...",
    essential = false,
    environment = [
      { name = "APP_ROLE", value = "correlator" },
      { name = "DATABASE_URL", value = var.db_file_path }
    ],
    mountPoints = [...],
    logConfiguration = {...}
  }
])
```

> Set `poller` and `correlator` as `essential = false` so a parser/correlator crash does not restart the API container.

#### C. Add an Application Load Balancer (optional)

If you want to expose the API publicly:

1. Create an ALB in public subnets.
2. Create a target group on port 8000.
3. Update the ECS service to use `load_balancer` configuration.
4. Add an ingress rule allowing ALB → ECS on port 8000.
5. Remove `assign_public_ip` from ECS tasks if you add a NAT Gateway.

For a personal scheduler with no external consumers, you can skip the ALB and keep `assign_public_ip = true`.

#### D. Standardize image tags

Use `sha-<full-sha>` instead of 5-char SHA. Add ECR lifecycle policy to delete images older than 30 days to avoid unbounded growth.

#### E. Build the backup image in CI too

Push `spend_sense:backup-<sha>` from `Dockerfile.backup` so the backup task is versioned alongside the app.

#### F. Remove unnecessary security group rule

The `ecs_allow_tls_self` ingress rule can be removed unless you add service-to-service HTTPS within the same SG.

---

## 5. Suggested Deployment Roadmap

| Phase | Work | Rationale |
|-------|------|-----------|
| **1. Fix the basics** | Fix Dockerfile CMD, fix Terraform task definition to run api+poller+correlator. | The current deployment is functionally broken (wrong command). |
| **2. Secure CI/CD** | Switch to OIDC, remove auto-merge, split into `ci.yml` + `cd.yml`, use GitHub Environments. | Reduces secret exposure and prevents accidental production changes. |
| **3. Improve testing** | Run full test suite in CI, mock Gmail API. | Catches regressions early. |
| **4. Add observability** | Add CloudWatch alarms for task stopped, backup failures, and (if ALB exists) 5xx rate. | You know when things break. |
| **5. Future: RDS** | Migrate from SQLite on EFS to RDS PostgreSQL if you need high availability or multiple API tasks. | SQLite on EFS is fine for personal use but has scaling limits. |

---

## 6. Decision Summary

| Question | Recommendation |
|----------|----------------|
| **OIDC or access keys?** | OIDC |
| **One task or three services?** | One task with three containers for now |
| **SQLite or RDS?** | Keep SQLite on EFS; plan RDS later |
| **Public IP or NAT Gateway?** | Public IP is fine for personal/low-budget |
| **ALB or no ALB?** | No ALB unless you need external API access |
| **Auto-merge?** | Remove it; require review + status checks |
| **Full tests or subset?** | Full test suite |
| **Image tag?** | `sha-<full-sha>` + semver for releases |

---

## 7. Next Step

I can implement these changes for you:

1. Rewrite `Dockerfile` CMD to honor `APP_ROLE`.
2. Refactor `deploy_1/main.tf` to run `api` + `poller` + `correlator` containers.
3. Replace `.github/workflows/cicd.yml` with `ci.yml` + `cd.yml` using OIDC.
4. Add a post-deploy smoke test step.

Would you like me to proceed with all of these, or start with a specific subset?
