# Task 4.1 Bootstrap Notes: Terraform State to S3

## Purpose
This document records the implementation of Task 4.1: the one-time bootstrap step to move Terraform state to an Amazon S3 backend.

## What was executed

### 1. Prerequisites check
Purpose: confirm that the environment can create and use the remote state backend.

Commands used:
```bash
terraform version
aws --version
aws sts get-caller-identity
```

Result: Terraform and AWS CLI were available, and AWS credentials were valid for the deployment account.

### 2. Create the AWS state backend resources
Purpose: create the storage and locking components required by Terraform remote state.

Commands used:
```bash
export AWS_DEFAULT_REGION=ap-southeast-1
BUCKET_NAME='spendsense-tfstate-359615771071'
TABLE_NAME='spendsense-tfstate-lock'

aws s3api create-bucket \
  --bucket "$BUCKET_NAME" \
  --region ap-southeast-1 \
  --create-bucket-configuration LocationConstraint=ap-southeast-1

aws s3api put-bucket-versioning \
  --bucket "$BUCKET_NAME" \
  --versioning-configuration Status=Enabled

aws s3api put-bucket-encryption \
  --bucket "$BUCKET_NAME" \
  --server-side-encryption-configuration '{"Rules": [{"ApplyServerSideEncryptionByDefault": {"SSEAlgorithm": "AES256"}}]}'

aws s3api put-public-access-block \
  --bucket "$BUCKET_NAME" \
  --public-access-block-configuration 'BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true'

aws dynamodb create-table \
  --table-name "$TABLE_NAME" \
  --attribute-definitions AttributeName=LockID,AttributeType=S \
  --key-schema AttributeName=LockID,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST
```

Result:
- S3 bucket created: `spendsense-tfstate-359615771071`
- DynamoDB table created: `spendsense-tfstate-lock`

### 3. Configure the Terraform backend
Purpose: tell Terraform to use the newly created S3 bucket and DynamoDB table for state storage and locking.

File created:
- `deploy_1/backend.tf`

Configuration added:
```hcl
terraform {
  backend "s3" {
    bucket         = "spendsense-tfstate-359615771071"
    key            = "spendsense/terraform.tfstate"
    region         = "ap-southeast-1"
    dynamodb_table = "spendsense-tfstate-lock"
    encrypt        = true
  }
}
```

### 4. Initialize Terraform with the remote backend
Purpose: switch Terraform from local state handling to the S3 remote backend and migrate the existing state from the deployment folder to S3.

Relevant context:
- There is an existing local Terraform state file in `deploy_1/terraform.tfstate`.
- The bootstrap used `terraform init -migrate-state -input=false` so Terraform could move the existing state into the new S3 backend.
- The state file was also uploaded manually to S3 with the AWS CLI as a fallback/explicit bootstrap step.

Command used:
```bash
terraform init -migrate-state -input=false
```

Manual upload command used:
```bash
aws s3 cp terraform.tfstate s3://spendsense-tfstate-359615771071/spendsense/terraform.tfstate
```

Result: Terraform reported that initialization completed successfully.

## Verification
The initialization completed successfully with the message:
```text
Terraform has been successfully initialized!
```

## Notes
- This step is a one-time bootstrap for remote state.
- After this, future Terraform runs should use the S3 backend instead of a local state file.
- The state is now managed remotely in S3 with DynamoDB locking.
