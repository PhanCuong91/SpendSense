# Task: Fix Terraform Deployment and State Management

## 1. Objective
Resolve the current Terraform deployment issue where terraform plan and terraform apply fail because no Terraform state file is available.

The task must ensure that:
- Terraform uses a remote state backend,
- the state is stored in Amazon S3,
- deployment can run successfully from GitHub Actions or a local CI/CD environment,
- and the workflow can recover from a missing state file in a controlled way.

## 2. Problem Statement
The current deployment pipeline cannot run terraform plan or terraform apply because Terraform cannot find a valid state file.

This usually happens when:
- the repository has no remote backend configured,
- the state file is missing locally,
- the S3 backend is not initialized,
- or the deployment environment does not have the correct AWS credentials and permissions.

## 3. Scope
This task covers:
- Deployment workflow steps for Terraform,
- Terraform remote state setup using S3,
- initialization of the backend before running plan/apply,
- and required prerequisites for successful deployment.

## 4. Required Tasks

### 4.1 One-Time State Migration / Initial Bootstrap [x]
This step must be performed first and should be treated as a one-time bootstrap.

Required behavior:
- Create or prepare the initial S3 bucket for Terraform state if it does not already exist.
- Upload the existing Terraform state to S3 once when migrating from local state.
- After this step, later runs should not repeat the same bootstrap work unless a new environment is created.

### 4.2 Backend Bootstrap for Remaining Remote-State Prerequisites [x]
After the initial state bootstrap is complete, prepare any remaining backend requirements.

Required actions:
1. Create a DynamoDB table for state locking if it does not already exist.
2. Grant the deployment principal the required IAM permissions to read and write the state.
3. Configure Terraform to use the S3 backend.

Execution status (2026-07-19):
- Verified S3 backend bucket exists and is accessible: `spendsense-tfstate-359615771071`.
- Verified DynamoDB lock table exists and is active: `spendsense-tfstate-lock`.
- Added Terraform backend configuration file: `deploy_1/backend.tf`.
- Added idempotent backend-prerequisite bootstrap script: `scripts/tf_backend_bootstrap.sh`.
	- Ensures DynamoDB lock table exists.
	- Creates/updates a least-privilege IAM policy for Terraform state access.
	- Attaches the policy to the deployment IAM principal (`DEPLOYMENT_PRINCIPAL_ARN`).

### 4.3 Deployment Workflow Update [x]
Update the deployment flow so that it uses the S3 remote backend consistently.

Required steps:
1. Validate the deployment environment.
2. Authenticate to AWS securely.
3. Initialize Terraform with the S3 backend.
4. Run terraform plan using the remote state.
5. Run terraform apply using the remote state.
6. Ensure the state is updated and persisted in S3 after deployment.

Execution status (2026-07-19):
- Updated `.github/workflows/cicd.yml` (`continuous-deployment` job):
  - Added a "Validate deployment environment" step that checks required env vars and secrets before doing any AWS/Terraform work.
  - Kept AWS authentication via `aws-actions/configure-aws-credentials`, added a "Verify AWS authentication" step (`aws sts get-caller-identity`) to fail fast on bad credentials.
  - Replaced the destructive `terraform destroy -auto-approve` + reapply pattern with `terraform init -input=false` against the S3 backend added in 4.2.
  - Added an idempotent secret-import step that only runs `terraform import` when a secret isn't already tracked in state (checked via `terraform state show`), instead of unconditionally destroying/recreating resources.
  - Split `terraform plan` (saved to a plan file) and `terraform apply` (applies that exact plan file) into separate steps, both with `-lock-timeout` and log inspection that surfaces a clear "state lock held" error message per section 5.3.
  - Added a "Capture pre-apply state version" step and a final "Verify Terraform state persisted in S3" step that compare the S3 object's `VersionId` before and after `terraform apply`, failing the job if the version did not change. This proves the S3 state object was actually rewritten by this deployment (not just that it exists), relying on the bucket versioning enabled during the 4.1 bootstrap.
- Validated the updated workflow YAML parses correctly with `python3 -c "import yaml; yaml.safe_load(...)"`.

### 4.4 Security Requirements [x]
- Do not commit secrets or credentials to the repository.
- Use GitHub OIDC or secure AWS credentials.
- Restrict S3 access to the deployment role only.

Execution status (2026-07-19):
- Confirmed via `git ls-files` that no credentials (`credentials.json`, `token.json`) or Terraform state/plan files are currently tracked in git.
- Hardened `.gitignore` with standard Terraform ignore rules (`*.tfstate*`, `**/.terraform/*`, `*.tfvars*`, `*tfplan*`, override files, CLI config), so state and plan artifacts can never be accidentally committed. `.terraform.lock.hcl` is intentionally still trackable (recommended practice).
- Applied a bucket policy on `spendsense-tfstate-359615771071` with two statements:
  1. `DenyInsecureTransport` — denies all S3 actions when `aws:SecureTransport` is false (enforces encryption-in-transit).
  2. `RestrictToDeploymentPrincipals` — denies all S3 actions for any principal other than `pcuong-IAM-Admin`, `pcuong-IAM-Admin1`, and the account root (root kept as a safety net to prevent irrecoverable lockout; confirmed with the user before applying).
- Verified after applying the policy that `terraform state list` and `aws s3api head-object` still work for the deployment principal — no lockout occurred.
- The deployment workflow already authenticates via GitHub Actions secrets (`AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY`), never hardcoded — satisfies "secure AWS credentials". Per user decision, GitHub OIDC migration was explicitly declined for now (no OIDC provider was created).

## 5. Implementation Notes

### 5.1 Backend Initialization
Before running Terraform, ensure the following exist:
- the initial S3 bucket for remote state from the one-time bootstrap,
- DynamoDB table for locking if required,
- proper IAM policy for the deployment principal.

### 5.2 Terraform Commands
The deployment workflow should run:
- terraform init
- terraform plan
- terraform apply

with configuration pointing to the S3 backend.

### 5.3 Failure Handling
If the backend is unavailable or credentials are invalid, the deployment should fail clearly with a useful error message.
If state locking is active, the workflow should report that another deployment is already in progress.

## 6. Acceptance Criteria
The task is complete when:
1. Terraform deployment can run without requiring a local terraform.tfstate file.
2. Terraform state is stored in Amazon S3.
3. Terraform init, plan, and apply work against the remote backend.
4. The deployment workflow handles a missing state file gracefully.
5. The deployment is secure and uses proper AWS authentication.

## 7. Suggested Next Steps
1. Perform the one-time state bootstrap first and upload the initial state to S3.
2. Create the DynamoDB lock table and grant IAM permissions if they are not already present.
3. Configure the Terraform backend to use S3.
4. Update the deployment workflow to use the remote backend.
5. Re-run terraform init, terraform plan, and terraform apply to verify the fix.
