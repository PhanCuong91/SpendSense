# CI/CD Pipeline — SpendSense

SpendSense uses **GitHub Actions** with a **label-based trigger** model. There is no automatic trigger on push or merge — all pipeline runs are initiated by applying a label to a Pull Request.

Pipeline file: `.github/workflows/cicd.yml`

---

## Pipeline Overview

```
Pull Request opened
        │
        ├── Apply label: "check"   ──► Process 1: Run Tests only
        │
        └── Apply label: "merge"   ──► Process 2: Run Tests + Auto-Merge
                                               │
                                               ▼
                                       Process 3: CD Deployment
                                         (AWS ECR + Terraform)
```

After every run (success or failure), the label is **automatically removed** by the `cleanup` job, so you can re-apply it to trigger the pipeline again.

---

## Process 1: `check` label — Run Tests

**Trigger:** Apply the `check` label to a PR.

**What happens:**
1. Checks out the PR branch
2. Sets up Python 3.13
3. Installs dependencies from `requirements.txt`
4. Runs:
   ```bash
   pytest -q tests/test_gmail_polling.py
   pytest -q tests/test_parser.py
   ```
5. Label is removed by `cleanup` job

**Required GitHub Secrets:**
| Secret | Purpose |
|--------|---------|
| `GMAIL_TOKEN_JSON` | Gmail OAuth2 token for test |
| `GMAIL_CREDENTIALS_JSON` | Gmail OAuth2 credentials for test |

**Use this when:** You want to validate a branch passes tests without merging.

---

## Process 2: `merge` label — Tests + Auto-Merge

**Trigger:** Apply the `merge` label to a PR.

**What happens:**
1. Checks out code
2. Sets up Python 3.13 + installs dependencies
3. Runs the same tests as `check`:
   ```bash
   pytest -q tests/test_gmail_polling.py
   pytest -q tests/test_parser.py
   ```
4. If tests pass: **auto-merges the PR** into `main` using `actions/github-script`
5. Outputs the merged commit SHA for Process 3

**Required GitHub Secrets:**
| Secret | Purpose |
|--------|---------|
| `TOKEN` | GitHub PAT with `repo` scope (for auto-merge) |
| `GMAIL_TOKEN_JSON` | Gmail OAuth2 token |
| `GMAIL_CREDENTIALS_JSON` | Gmail OAuth2 credentials |

---

## Process 3: Continuous Deployment

**Trigger:** Runs automatically after Process 2 succeeds (after merge).

**What happens:**

### Step 1 — Validate environment
Checks that all required secrets are present:
- `AWS_REGION`, `PROJECT_NAME`
- `GMAIL_CREDENTIALS_JSON`, `GMAIL_TOKEN_JSON`
- `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`

### Step 2 — AWS Login
```bash
aws-actions/configure-aws-credentials@v3
Region: ap-southeast-1
```

### Step 3 — Build & Push Docker image to ECR
```bash
# Image tag = first 5 chars of merged commit SHA
docker build -t spend_sense:<TAG> .
docker tag spend_sense:<TAG> 359615771071.dkr.ecr.ap-southeast-1.amazonaws.com/spend_sense:<TAG>
docker push 359615771071.dkr.ecr.ap-southeast-1.amazonaws.com/spend_sense:<TAG>
```

### Step 4 — Terraform Init (S3 remote backend)
```bash
cd deploy_1
terraform init -input=false
```
Remote state: `s3://spendsense-tfstate-359615771071/spendsense/terraform.tfstate`

### Step 5 — Import existing AWS resources (idempotent)
Safely imports existing AWS Secrets Manager secrets and SSM parameters into Terraform state if not already tracked. Prevents "resource already exists" errors on re-deployments.

Resources checked:
- `aws_secretsmanager_secret.gmail_credentials`
- `aws_secretsmanager_secret.gmail_token`
- `aws_ssm_parameter.misa_username[0]`
- `aws_ssm_parameter.misa_password[0]`

### Step 6 — Terraform Plan
```bash
terraform plan -var="app_image_tag=<TAG>" -out=tfplan
```

### Step 7 — Terraform Apply
```bash
terraform apply -auto-approve tfplan
```

### Step 8 — Verify state persistence
Checks that the S3 state file version changed after apply — confirms the state was successfully written.

---

## Required GitHub Secrets

Go to **Settings → Secrets and variables → Actions** in your GitHub repo.

| Secret Name | Description |
|-------------|-------------|
| `GMAIL_CREDENTIALS_JSON` | Full `credentials.json` contents |
| `GMAIL_TOKEN_JSON` | Full `token.json` contents |
| `TOKEN` | GitHub PAT with `repo` + `pull_request` write scope |
| `AWS_ACCESS_KEY_ID` | AWS IAM access key |
| `AWS_SECRET_ACCESS_KEY` | AWS IAM secret key |

---

## Reusable Workflow: `python-test.yml`

The `check` label process calls this as a reusable workflow:
- Sets up Python 3.13
- Installs `requirements.txt`
- Runs the command passed via the `command` input
- Injects `GMAIL_TOKEN_JSON` and `GMAIL_CREDENTIALS_JSON` as env vars

---

## Label Cleanup

After every run (success or failure), `.github/workflows/remove-label.yml` removes the triggering label from the PR automatically. This allows re-triggering the same pipeline by simply re-applying the label.

---

## CI Environment Variables

These are set automatically in CI (not required in GitHub Secrets):

| Variable | Value | Description |
|----------|-------|-------------|
| `POLL_ONCE` | `true` | Prevents poller from looping infinitely |
| `PYTHONPATH` | `src` | Python module path |

---

## Pipeline Diagram

```
PR labeled "merge"
    │
    ▼
[merge-label job]
    ├── checkout
    ├── setup Python 3.13
    ├── pip install -r requirements.txt
    ├── pytest test_gmail_polling.py
    ├── pytest test_parser.py
    └── github-script: merge PR → outputs merged_sha
              │
              ▼
[continuous-deployment job]
    ├── IMAGE_TAG = merged_sha[:5]
    ├── checkout (merged commit)
    ├── validate secrets
    ├── setup-terraform
    ├── configure-aws-credentials
    ├── docker build + tag + push → ECR
    ├── terraform init (S3 backend)
    ├── import existing secrets (idempotent)
    ├── terraform plan -var app_image_tag=<TAG>
    ├── capture pre-apply state version
    ├── terraform apply
    └── verify S3 state version changed

[cleanup job] (always runs)
    └── remove-label.yml → removes "merge" label from PR
```
