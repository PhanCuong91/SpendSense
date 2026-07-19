#!/usr/bin/env bash
set -euo pipefail

AWS_REGION="${AWS_REGION:-ap-southeast-1}"
ACCOUNT_ID="${ACCOUNT_ID:-$(aws sts get-caller-identity --query Account --output text)}"
TF_STATE_BUCKET="${TF_STATE_BUCKET:-spendsense-tfstate-${ACCOUNT_ID}}"
TF_LOCK_TABLE="${TF_LOCK_TABLE:-spendsense-tfstate-lock}"
TF_STATE_KEY_PREFIX="${TF_STATE_KEY_PREFIX:-spendsense}"
TF_STATE_POLICY_NAME="${TF_STATE_POLICY_NAME:-SpendSenseTerraformStateAccess}"
DEPLOYMENT_PRINCIPAL_ARN="${DEPLOYMENT_PRINCIPAL_ARN:-$(aws sts get-caller-identity --query Arn --output text)}"

echo "[info] region=${AWS_REGION}"
echo "[info] account_id=${ACCOUNT_ID}"
echo "[info] state_bucket=${TF_STATE_BUCKET}"
echo "[info] lock_table=${TF_LOCK_TABLE}"
echo "[info] deployment_principal=${DEPLOYMENT_PRINCIPAL_ARN}"

echo "[step] verify S3 state bucket access"
aws s3api head-bucket --bucket "${TF_STATE_BUCKET}" >/dev/null

echo "[step] ensure DynamoDB lock table exists"
if aws dynamodb describe-table --table-name "${TF_LOCK_TABLE}" --region "${AWS_REGION}" >/dev/null 2>&1; then
  echo "[ok] DynamoDB table already exists"
else
  aws dynamodb create-table \
    --table-name "${TF_LOCK_TABLE}" \
    --attribute-definitions AttributeName=LockID,AttributeType=S \
    --key-schema AttributeName=LockID,KeyType=HASH \
    --billing-mode PAY_PER_REQUEST \
    --region "${AWS_REGION}" >/dev/null
  aws dynamodb wait table-exists --table-name "${TF_LOCK_TABLE}" --region "${AWS_REGION}"
  echo "[ok] DynamoDB table created"
fi

POLICY_ARN="arn:aws:iam::${ACCOUNT_ID}:policy/${TF_STATE_POLICY_NAME}"
POLICY_DOC_FILE="$(mktemp)"

cat >"${POLICY_DOC_FILE}" <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "TerraformStateBucketAccess",
      "Effect": "Allow",
      "Action": [
        "s3:ListBucket",
        "s3:GetBucketVersioning"
      ],
      "Resource": "arn:aws:s3:::${TF_STATE_BUCKET}"
    },
    {
      "Sid": "TerraformStateObjectAccess",
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:DeleteObject",
        "s3:GetObjectVersion"
      ],
      "Resource": "arn:aws:s3:::${TF_STATE_BUCKET}/${TF_STATE_KEY_PREFIX}/*"
    },
    {
      "Sid": "TerraformLockTableAccess",
      "Effect": "Allow",
      "Action": [
        "dynamodb:DescribeTable",
        "dynamodb:GetItem",
        "dynamodb:PutItem",
        "dynamodb:DeleteItem",
        "dynamodb:UpdateItem"
      ],
      "Resource": "arn:aws:dynamodb:${AWS_REGION}:${ACCOUNT_ID}:table/${TF_LOCK_TABLE}"
    }
  ]
}
EOF

echo "[step] ensure IAM policy exists and is current"
if aws iam get-policy --policy-arn "${POLICY_ARN}" >/dev/null 2>&1; then
  CURRENT_VERSION_ID="$(aws iam get-policy --policy-arn "${POLICY_ARN}" --query 'Policy.DefaultVersionId' --output text)"
  CURRENT_DOC="$(aws iam get-policy-version --policy-arn "${POLICY_ARN}" --version-id "${CURRENT_VERSION_ID}" --query 'PolicyVersion.Document' --output json)"
  TARGET_DOC="$(cat "${POLICY_DOC_FILE}")"

  if [[ "${CURRENT_DOC}" != "${TARGET_DOC}" ]]; then
    NON_DEFAULT_COUNT="$(aws iam list-policy-versions --policy-arn "${POLICY_ARN}" --query 'length(Versions[?IsDefaultVersion==`false`])' --output text)"
    if [[ "${NON_DEFAULT_COUNT}" -ge 4 ]]; then
      OLDEST_NON_DEFAULT="$(aws iam list-policy-versions --policy-arn "${POLICY_ARN}" --query 'sort_by(Versions[?IsDefaultVersion==`false`], &CreateDate)[0].VersionId' --output text)"
      aws iam delete-policy-version --policy-arn "${POLICY_ARN}" --version-id "${OLDEST_NON_DEFAULT}"
    fi

    aws iam create-policy-version \
      --policy-arn "${POLICY_ARN}" \
      --policy-document "file://${POLICY_DOC_FILE}" \
      --set-as-default >/dev/null
    echo "[ok] Updated IAM policy default version"
  else
    echo "[ok] IAM policy already up to date"
  fi
else
  aws iam create-policy \
    --policy-name "${TF_STATE_POLICY_NAME}" \
    --policy-document "file://${POLICY_DOC_FILE}" >/dev/null
  echo "[ok] Created IAM policy ${TF_STATE_POLICY_NAME}"
fi

PRINCIPAL_TYPE="${DEPLOYMENT_PRINCIPAL_ARN#arn:aws:iam::${ACCOUNT_ID}:}"

echo "[step] attach IAM policy to deployment principal"
case "${PRINCIPAL_TYPE}" in
  user/*)
    PRINCIPAL_NAME="${PRINCIPAL_TYPE#user/}"
    aws iam attach-user-policy --user-name "${PRINCIPAL_NAME}" --policy-arn "${POLICY_ARN}"
    ;;
  role/*)
    PRINCIPAL_NAME="${PRINCIPAL_TYPE#role/}"
    aws iam attach-role-policy --role-name "${PRINCIPAL_NAME}" --policy-arn "${POLICY_ARN}"
    ;;
  *)
    echo "[error] Unsupported deployment principal ARN format: ${DEPLOYMENT_PRINCIPAL_ARN}" >&2
    echo "[hint] Provide a direct IAM user or IAM role ARN using DEPLOYMENT_PRINCIPAL_ARN" >&2
    rm -f "${POLICY_DOC_FILE}"
    exit 1
    ;;
esac

rm -f "${POLICY_DOC_FILE}"
echo "[done] Terraform remote-state prerequisites are configured"