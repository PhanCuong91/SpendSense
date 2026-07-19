# Design for CI, PR Label Checks, and Terraform State Management

## 1. Objective
This design describes how to implement a GitHub-based CI/CD workflow for the project, including:
- PR validation with automated checks,
- merge protection through required labels,
- deployment after merge to the main branch,
- and Terraform state storage in Amazon S3.

## 2. Scope
The solution covers:
- GitHub Actions workflows for CI and deployment,
- branch protection rules for merge enforcement,
- Terraform remote backend configuration using S3,
- secure authentication to AWS from GitHub Actions,
- and state management practices that avoid committing local state files.

## 3. Architecture Overview

### 3.1 Components
- GitHub repository
  - holds source code and workflow definitions
- GitHub Actions
  - runs CI checks on pull requests
  - runs deployment after merge to main
- AWS
  - provides the S3 bucket for Terraform state
  - provides DynamoDB for state locking
- Terraform
  - provisions infrastructure using remote state

### 3.2 High-Level Flow
1. A developer opens a pull request.
2. GitHub Actions runs tests, linting, and validation checks.
3. The workflow checks whether the PR has the required label.
4. If checks or label validation fail, merge is blocked.
5. After merge to main, the deployment workflow runs.
6. Terraform initializes using the S3 remote backend.
7. Terraform plan and apply run against the remote state.
8. Terraform state is stored in S3 after deployment.

## 4. CI Workflow Design

### 4.1 Trigger
- Trigger on pull_request to the main branch.
- Trigger on push to main for deployment.

### 4.2 Required Checks
The CI workflow must run:
- unit tests,
- linting and formatting checks,
- build validation,
- smoke tests if available.

### 4.3 Label Enforcement
The workflow should inspect PR labels and fail if the required label is missing.
Example required labels:
- ready-to-merge
- approved
- release

### 4.4 Merge Protection
Branch protection on main should require:
- all CI checks to pass,
- the label check to pass,
- and no pending review blockers.

## 5. Deployment Workflow Design

### 5.1 Trigger
- Trigger on push to main after a PR is merged.
- Optionally support manual dispatch for staging or production.

### 5.2 Deployment Steps
1. Validate environment.
2. Authenticate to AWS.
3. Download the current Terraform state from the S3 backend if it exists.
4. Initialize Terraform using the S3 remote backend.
5. Run terraform plan using the state downloaded from S3.
6. Run terraform apply using the same remote state.
7. Persist and update the Terraform state in the S3 backend after deployment.

### 5.3 Environment Strategy
- staging: can run automatically or with limited approval.
- production: should require explicit approval before apply.

## 6. Terraform State Design

### 6.1 Backend Choice
Terraform will use an Amazon S3 backend.

### 6.2 Backend Prerequisites
Before the first Terraform run, the following must exist:
- an S3 bucket for storing the state file,
- a DynamoDB table for state locking,
- appropriate IAM permissions for the GitHub Actions role.

### 6.3 State Storage Behavior
- Terraform state is not stored in the GitHub repository.
- Terraform state is stored in S3 after deployment.
- The state file is read and updated remotely during Terraform operations.

### 6.4 Locking Behavior
- Terraform uses DynamoDB locking to avoid concurrent apply operations.
- If another deployment is running, later runs must wait or fail clearly.

### 6.5 Security Considerations
- Use GitHub OIDC or stored AWS credentials securely.
- Restrict bucket access to the deployment role.
- Avoid committing terraform.tfstate or local state artifacts to GitHub.

## 7. Security Design

### 7.1 Secret Handling
- Do not commit secrets to the repository.
- Use GitHub Actions secrets or OIDC for AWS access.
- Keep credentials scoped to the minimum required permissions.

### 7.2 Access Control
- Only the deployment role should access the Terraform state bucket.
- State bucket policies should restrict access to approved environments.

## 8. Operational Design

### 8.1 Logging and Traceability
- GitHub Actions logs should clearly show:
  - CI status,
  - label validation result,
  - Terraform init/plan/apply output,
  - deployment success or failure.

### 8.2 Failure Handling
- If the remote backend is unavailable, the workflow should fail clearly.
- If authentication fails, deployment should stop before Terraform changes are applied.
- If a lock is already held, the workflow should report the conflict.

## 9. Acceptance Criteria
The design is considered complete when:
1. Pull requests trigger CI checks automatically.
2. PRs without the required label fail the label validation step.
3. Merge is blocked until required checks and labels pass.
4. Merging to main triggers deployment.
5. Terraform uses an S3 remote backend for state.
6. Terraform state is stored in S3 after deployment and is not stored in GitHub.
