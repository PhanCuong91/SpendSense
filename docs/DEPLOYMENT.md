# Deployment Guide — SpendSense

SpendSense is deployed to **AWS** using **Terraform** for infrastructure and **GitHub Actions** for CI/CD. The infrastructure is defined in `deploy_1/`.

See also: [`deploy_1/ARCHITECTURE.md`](../deploy_1/ARCHITECTURE.md) for detailed Terraform resource descriptions.

---

## Infrastructure Overview

| Component | AWS Service |
|-----------|-------------|
| Container image registry | Amazon ECR |
| Container runtime | Amazon ECS (Fargate or EC2) |
| Secrets & Credentials | AWS Systems Manager (SSM) Parameter Store |
| Terraform remote state | Amazon S3 (`spendsense-tfstate-359615771071`) |
| Region | `ap-southeast-1` (Singapore) |

---

## Prerequisites

- AWS CLI configured with appropriate credentials
- Terraform 1.9.0+ installed
- Docker installed (for image builds)
- S3 backend bucket already bootstrapped (run once: `scripts/tf_backend_bootstrap.sh`)

---

## Bootstrap (First Time Only)

Run the S3 backend bootstrap script once before the first Terraform deployment:

```bash
bash scripts/tf_backend_bootstrap.sh
```

This creates:
- The S3 bucket for Terraform state (`spendsense-tfstate-359615771071`)
- DynamoDB table for state locking (if used)

---

## Manual Deployment

If you need to deploy manually (outside of GitHub Actions):

### 1. Build and push Docker image to ECR

```bash
IMAGE_TAG=<your-tag>
AWS_ACCOUNT=359615771071
AWS_REGION=ap-southeast-1
ECR_REPO=$AWS_ACCOUNT.dkr.ecr.$AWS_REGION.amazonaws.com/spend_sense

# Login to ECR
aws ecr get-login-password --region $AWS_REGION \
  | docker login --username AWS --password-stdin $AWS_ACCOUNT.dkr.ecr.$AWS_REGION.amazonaws.com

# Build and push
docker build -t spend_sense:$IMAGE_TAG .
docker tag spend_sense:$IMAGE_TAG $ECR_REPO:$IMAGE_TAG
docker push $ECR_REPO:$IMAGE_TAG
```

### 2. Apply Terraform

```bash
cd deploy_1

# Initialize (connects to S3 remote state)
terraform init

# Plan with the new image tag
terraform plan -var="app_image_tag=$IMAGE_TAG"

# Apply
terraform apply -var="app_image_tag=$IMAGE_TAG" -auto-approve
```

---

## Secrets Setup

All secrets are stored in **AWS Systems Manager (SSM) Parameter Store** as `SecureString` parameters (encrypted at rest with KMS) to stay 100% within the free tier.

### Gmail credentials (SSM Parameter Store)

The GitHub Actions CI/CD pipeline reads Gmail credentials from GitHub Secrets and passes them to Terraform as `TF_VAR_*`. Terraform stores them in AWS SSM Parameter Store as `SecureString`.

| Terraform variable | AWS SSM Parameter name | Type |
|-------------------|------------------------|------|
| `TF_VAR_gmail_credentials_json` | `/spendsense/gmail_credentials_json` | `SecureString` |
| `TF_VAR_gmail_token_json` | `/spendsense/gmail_token_json` | `SecureString` |

### MISA credentials (SSM Parameter Store)

| SSM Parameter | Description |
|---------------|-------------|
| `/spendsense/misa_username` | MISA login email |
| `/spendsense/misa_password` | MISA login password |

To set them manually:
```bash
aws ssm put-parameter \
  --name /spendsense/misa_username \
  --value "your@email.com" \
  --type SecureString \
  --region ap-southeast-1

aws ssm put-parameter \
  --name /spendsense/misa_password \
  --value "your_password" \
  --type SecureString \
  --region ap-southeast-1
```

---

## Terraform Files (`deploy_1/`)

| File | Purpose |
|------|---------|
| `main.tf` | Core infrastructure (ECR, ECS, VPC, IAM, SSM Parameter Store) |
| `misa_runner.tf` | MISA runner ECS task definition and scheduled job |
| `variables.tf` | Input variables |
| `outputs.tf` | Output values (e.g. ECR repo URL) |
| `backend.tf` | S3 remote state configuration |
| `terraform.tfvars.example` | Example variable values |

---

## Terraform Remote State

```hcl
# deploy_1/backend.tf
terraform {
  backend "s3" {
    bucket = "spendsense-tfstate-359615771071"
    key    = "spendsense/terraform.tfstate"
    region = "ap-southeast-1"
  }
}
```

> ⚠️ The state lock is managed via S3 object versioning. If a deployment fails and the lock is stuck, check S3 for the state file version and resolve manually.

---

## IAM Permissions Required

The deploying IAM user/role needs:

```
ecr:GetAuthorizationToken
ecr:BatchCheckLayerAvailability
ecr:PutImage / ecr:InitiateLayerUpload / ecr:UploadLayerPart / ecr:CompleteLayerUpload
ecs:RegisterTaskDefinition / ecs:UpdateService / ecs:DescribeServices
secretsmanager:CreateSecret / secretsmanager:UpdateSecret / secretsmanager:DescribeSecret
ssm:PutParameter / ssm:GetParameter / ssm:DescribeParameters
s3:GetObject / s3:PutObject (on tfstate bucket)
sts:GetCallerIdentity
```

---

## Rollback

To rollback to a previous image tag:

```bash
cd deploy_1
terraform apply -var="app_image_tag=<previous-tag>" -auto-approve
```

Or restore the previous Terraform state from S3 versioning if the state itself was corrupted.

---

## Automated CI/CD

The preferred way to deploy is via the **`merge` label** on GitHub. See [`docs/CICD.md`](CICD.md) for the full pipeline documentation.

---

## AWS Resource Diagram

> Rendered with any PlantUML viewer — IntelliJ plugin, VS Code PlantUML extension, or [plantuml.com](https://www.plantuml.com/plantuml/uml/).

### Diagram 1 — Main Flow (Task Chain)

```plantuml
@startuml SpendSense_Main_Flow
!theme plain
left to right direction

skinparam defaultFontName Helvetica
skinparam defaultFontSize 10
skinparam ArrowThickness 1.5
skinparam ArrowColor #555555
skinparam RoundCorner 8
skinparam Padding 10
skinparam nodesep 90
skinparam ranksep 110
skinparam linetype ortho

skinparam package {
    BackgroundColor #FAFAFA
    BorderColor #BBBBBB
    FontStyle bold
    FontSize 11
    Padding 14
}
skinparam rectangle {
    BorderThickness 1.5
}
skinparam database {
    BorderThickness 1.5
}

package "CI / Deploy" {
    rectangle "GitHub Actions\nPR label: check / merge\ncicd.yml" as GH #FFF3E0
    rectangle "Amazon ECR\nRepo: spend_sense\nTag = SHA[:5]" as ECR #FFF3E0
    rectangle "S3 - Terraform State\nspendsense-tfstate-*" as TFS3 #E8F5E9
}

package "Secrets (SSM Parameter Store)" {
    rectangle "SSM: Gmail\n/spendsense/gmail_credentials_json\n/spendsense/gmail_token_json" as SSM_GMAIL #FFEBEE
    rectangle "SSM: MISA\n/spendsense/misa_username\n/spendsense/misa_password" as SSM_MISA #FFEBEE
}

package "AppAutoscaling Schedule" {
    rectangle "Start 22:00 SGT\ncron(00 14 * * ? *)" as START #FFFDE7
    rectangle "Stop 22:20 SGT\ncron(20 14 * * ? *)" as STOP #FFFDE7
}

package "ECS Cluster (Fargate)" {
    rectangle "Poller Worker\nAPP_ROLE=poller\n512 CPU / 1024 MB\nRestore SQLite from S3 on cold start" as POLLER #E3F2FD
    rectangle "MISA Runner\nAPP_ROLE=misa\n1024 CPU / 2048 MB\nPlaywright Chromium headless\n--start-date yesterday --end-date today" as MISA #E3F2FD
    rectangle "Backup Task\nImage: backup-efs-amd64\n512 CPU / 1024 MB" as BACKUP #E3F2FD
}

package "EventBridge Rules" {
    rectangle "app_task_stopped\nECS STOPPED on spendsense-service" as EB1 #FFFDE7
    rectangle "misa_task_stopped\nECS STOPPED on misa-task" as EB2 #FFFDE7
}

package "Storage" {
    database "Amazon EFS\ntxdb.sqlite3\nMount: /app/data\nEncrypted + TLS transit" as EFS #E8F5E9
    rectangle "S3 - SQLite Backup\nspensense-db-*\ntxdb.sqlite3" as BKS3 #E8F5E9
}

package "Monitoring" {
    rectangle "CloudWatch Logs\n/ecs/spendsense\n/ecs/spendsense-misa\nRetention: 14 days" as CW #FCE4EC
    rectangle "CW Alarm\nfilter: [failed]\nSum > 0 per 300s" as ALARM #FCE4EC
    rectangle "SNS Topic\nemail subscription" as SNS #FCE4EC
}

GH     -[#FB8C00]->  ECR       : docker push
GH     -[#43A047]->  TFS3      : terraform apply
GH     -[#E53935]->  SSM_GMAIL : writes secrets

ECR    -[#1E88E5]->  POLLER    : image pull
ECR    -[#1E88E5]->  MISA      : image pull
ECR    -[#1E88E5]->  BACKUP    : image pull

SSM_GMAIL -[#E53935]-> POLLER  : GMAIL_CREDENTIALS_JSON\nGMAIL_TOKEN_JSON
SSM_MISA  -[#E53935]-> MISA    : MISA_USERNAME\nMISA_PASSWORD

START  -[#F9A825]->  POLLER : desired_count 0 to 1
STOP   -[#F9A825]->  POLLER : desired_count 1 to 0

POLLER -[#F9A825]->  EB1    : Task State Change STOPPED
EB1    -[#F9A825]->  MISA   : ecs:RunTask
MISA   -[#F9A825]->  EB2    : Task State Change STOPPED
EB2    -[#F9A825]->  BACKUP : ecs:RunTask

POLLER -[#43A047]->  EFS    : mount r/w /app/data
MISA   -[#43A047]->  EFS    : mount read /app/data
BACKUP -[#43A047]->  EFS    : mount read /app/data

BKS3   -[#43A047]->  POLLER : restore on cold start
BACKUP -[#43A047]->  BKS3   : s3 cp txdb.sqlite3

POLLER -[#D81B60]->  CW     : awslogs
MISA   -[#D81B60]->  CW     : awslogs
BACKUP -[#D81B60]->  CW     : awslogs
CW     -[#D81B60]->  ALARM  : metric filter
ALARM  -[#D81B60]->  SNS    : alarm action

@enduml
```

---

### Diagram 2 — Security and IAM

```plantuml
@startuml SpendSense_Security_IAM
!theme plain
left to right direction

skinparam defaultFontName Helvetica
skinparam defaultFontSize 10
skinparam ArrowThickness 1.5
skinparam ArrowColor #555555
skinparam RoundCorner 8
skinparam Padding 10
skinparam nodesep 90
skinparam ranksep 110
skinparam linetype ortho

skinparam package {
    BackgroundColor #FAFAFA
    BorderColor #BBBBBB
    FontStyle bold
    FontSize 11
    Padding 14
}
skinparam rectangle {
    BorderThickness 1.5
}
skinparam database {
    BorderThickness 1.5
}

package "IAM Roles" {
    rectangle "ecs-execution-role\nECR pull\nSSM Parameter Store read" as EXEC_ROLE #F3E5F5
    rectangle "ecs-task-role\nS3 PutObject\nS3 GetObject (backup bucket)" as TASK_ROLE #F3E5F5
    rectangle "misa-task-role\nSSM GetParameter\n(misa credentials only)" as MISA_ROLE #F3E5F5
    rectangle "eventbridge-ecs-role\necs:RunTask\niam:PassRole" as EB_ROLE #F3E5F5
}

package "Secrets and Config (SSM Parameter Store)" {
    rectangle "SSM: Gmail\n/spendsense/gmail_credentials_json\n/spendsense/gmail_token_json" as SSM_GMAIL #FFEBEE
    rectangle "SSM: MISA\n/spendsense/misa_username\n/spendsense/misa_password" as SSM_MISA #FFEBEE
}

package "VPC  ap-southeast-1  (vpc-0e67ef784)" {
    rectangle "ecs-sg\nEgress: 0.0.0.0/0 all\nIngress: TCP 443 from self" as ECS_SG #ECEFF1
    rectangle "efs-sg\nIngress: TCP 2049 NFS\nSource: ecs-sg only" as EFS_SG #ECEFF1
}

package "ECS Tasks" {
    rectangle "Poller Worker\nAPP_ROLE=poller" as POLLER #E3F2FD
    rectangle "MISA Runner\nAPP_ROLE=misa" as MISA #E3F2FD
    rectangle "Backup Task" as BACKUP #E3F2FD
}

package "Storage" {
    database "Amazon EFS\n/app/data" as EFS #E8F5E9
}

package "EventBridge" {
    rectangle "app_task_stopped\nmisa_task_stopped" as EB #FFFDE7
}

rectangle "Amazon ECR\nspend_sense repo" as ECR #FFF3E0

EXEC_ROLE -[#8E24AA]->  POLLER : execution role
EXEC_ROLE -[#8E24AA]->  MISA   : execution role
EXEC_ROLE -[#8E24AA]->  BACKUP : execution role

TASK_ROLE -[#8E24AA]->  POLLER : task role (S3 r/w)
TASK_ROLE -[#8E24AA]->  BACKUP : task role (S3 r/w)

MISA_ROLE -[#8E24AA]->  MISA   : task role (SSM read)

EB_ROLE   -[#8E24AA]->  EB     : RunTask permission

SSM_GMAIL -[#E53935]->  POLLER : GMAIL_CREDENTIALS_JSON\nGMAIL_TOKEN_JSON
SSM_MISA  -[#E53935]->  MISA   : MISA_USERNAME\nMISA_PASSWORD

ECR   -[#FB8C00]->  POLLER : image pull
ECR   -[#FB8C00]->  MISA   : image pull
ECR   -[#FB8C00]->  BACKUP : image pull

ECS_SG -[#78909C]->  POLLER : sg attached
ECS_SG -[#78909C]->  MISA   : sg attached
ECS_SG -[#78909C]->  BACKUP : sg attached

EFS_SG -[#78909C]->  EFS    : guards NFS port 2049

POLLER -[#43A047]->  EFS    : mount r/w
MISA   -[#43A047]->  EFS    : mount read
BACKUP -[#43A047]->  EFS    : mount read

@enduml
```
