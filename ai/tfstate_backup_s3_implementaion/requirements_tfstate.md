# Requirements for CI, PR Label Checks, and Terraform Deployment

## 1. Overview
This project requires a GitHub-based CI/CD flow that:
- runs automated checks for every pull request,
- enforces PR label requirements before merge,
- deploys the application automatically after the PR is merged,
- and uses a Terraform remote state backend so that terraform.tfstate is not stored in GitHub.

## 2. Functional Requirements

### 2.1 Pull Request CI Checks
1. GitHub Actions must run on every pull request to the main branch.
2. The CI workflow must run at least the following checks:
   - unit tests,
   - linting/formatting checks,
   - build validation,
   - any relevant smoke tests.
3. The workflow must fail if any required check fails.
4. The PR must be blocked from merging if required checks are not passing.

### 2.2 PR Label Validation
1. The GitHub workflow must verify that the PR has one or more required labels before merge.
2. Example required labels may include:
   - merge -> merge the PR
   - check -> check the PR
3. If the required label is missing, the workflow must fail and prevent merge.
4. The label check must be part of the required status checks enforced by GitHub branch protection.

### 2.3 Deployment After Merge
1. When a PR is merged into the main branch, a deployment workflow must be triggered automatically.
2. The deployment workflow must run only from the main branch after successful merge.
3. The deployment process must include:
   - environment validation,
   - Terraform initialization,
   - Terraform plan,
   - Terraform apply.
4. The deployment workflow must support staging and production environments, with production deployment requiring explicit approval if needed.

### 2.4 Terraform State Management
1. Terraform must not rely on a local terraform.tfstate file stored in the repository.
2. Terraform must use an Amazon S3 remote backend for state storage.
3. The S3 bucket and its locking support (typically DynamoDB) must be provisioned before the first Terraform init/apply, because Terraform cannot configure a backend in a bucket that does not exist yet.
4. After deployment, the Terraform state file must be stored in Amazon S3.
5. The backend must support state locking to prevent concurrent apply operations.
6. The workflow must authenticate securely to the remote backend using GitHub OIDC, secrets, or other approved secure mechanisms.
7. The repository must never contain terraform.tfstate files or other state artifacts.

## 3. Non-Functional Requirements

### 3.1 Security
1. No credentials, tokens, or secrets must be committed to the repository.
2. Terraform credentials must be injected through GitHub Actions secrets or OIDC.
3. State access must be restricted to the deployment environment and authorized users only.

### 3.2 Reliability
1. Terraform apply must be idempotent and safe to run repeatedly.
2. The deployment workflow must fail clearly when the backend is unavailable or authentication is invalid.
3. State locking must prevent two deployments from changing infrastructure at the same time.

### 3.3 Traceability
1. Every deployment must be trackable from GitHub Actions logs and PR history.
2. The workflow should publish deployment status back to GitHub checks or deployments.
3. Important deployment steps should be logged clearly for auditability.

## 4. Acceptance Criteria
The solution is considered complete when:
1. PRs trigger CI checks automatically.
2. PRs without the required label fail the label check.
3. Merge is blocked until all required checks pass and labels are validated.
4. Merging to main triggers the deployment workflow.
5. Terraform uses a remote backend for state storage.
6. terraform.tfstate is not stored in GitHub and is managed securely through the remote backend.

## 5. Recommended Implementation Approach
1. Use GitHub Actions for CI and deployment workflows.
2. Configure branch protection rules on the main branch.
3. Require status checks and labels before merge.
4. Configure Terraform remote backend before deployment.
5. Use GitHub OIDC or secrets for backend authentication.
6. Add .gitignore rules to prevent committing terraform.tfstate and related local files.
