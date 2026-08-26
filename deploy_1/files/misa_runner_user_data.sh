#!/bin/bash -euxo pipefail
# User-data for the MISA import runner EC2 instance.
# See ai/update_misa_implementation/misa_deployment_design.md for the design.

exec > >(tee /var/log/misa-runner-user-data.log) 2>&1

REGION="${region}"
BUCKET="${bucket}"
DB_KEY="${db_key}"
DB_DIR="/mnt/data"
DB_PATH="$DB_DIR/$DB_KEY"
IMAGE="${image}"
USERNAME_PARAM_NAME="${username_param_name}"
PASSWORD_PARAM_NAME="${password_param_name}"
LOG_GROUP="${log_group}"

INSTANCE_ID=$(curl -sf http://169.254.169.254/latest/meta-data/instance-id)

mkdir -p "$DB_DIR"

# Install Docker if it is not already present (Amazon Linux 2023 may have it).
if ! command -v docker &>/dev/null; then
  dnf update -y
  dnf install -y docker
  systemctl enable --now docker
fi

# Ensure the ec2-user can run docker for debugging.
usermod -aG docker ec2-user || true

aws s3 cp "s3://$BUCKET/$DB_KEY" "$DB_PATH"

aws ecr get-login-password --region "$REGION" | docker login --username AWS \
  --password-stdin "$(echo "$IMAGE" | cut -d/ -f1)"

docker pull "$IMAGE"

# Install Playwright Chromium inside the container; browsers are NOT baked
# into the image to keep it small.
docker run --rm \
  -v "$DB_DIR:/app/data" \
  "$IMAGE" \
  playwright install chromium

START_DATE=$(date -d 'yesterday' +%Y-%m-%d)
END_DATE=$(date +%Y-%m-%d)

set +e
docker run --rm \
  --log-driver=awslogs \
  --log-opt "awslogs-region=$REGION" \
  --log-opt "awslogs-group=$LOG_GROUP" \
  --log-opt "awslogs-stream-prefix=misa" \
  -e APP_ROLE=misa \
  -e DATABASE_URL=sqlite:///./data/txdb.sqlite3 \
  -e MISA_USERNAME_PARAM_NAME="$USERNAME_PARAM_NAME" \
  -e MISA_PASSWORD_PARAM_NAME="$PASSWORD_PARAM_NAME" \
  -v "$DB_DIR:/app/data" \
  "$IMAGE" \
  python -m app.misa.runner --start-date "$START_DATE" --end-date "$END_DATE"
RUN_EXIT=$?
set -e

if [[ $RUN_EXIT -eq 0 ]]; then
  aws s3 cp "$DB_PATH" "s3://$BUCKET/$DB_KEY"
  echo "Import succeeded; uploaded updated DB to s3://$BUCKET/$DB_KEY"
else
  echo "Import failed with exit code $RUN_EXIT; NOT uploading DB"
fi

# Stop this instance regardless of import outcome. Failed rows remain
# unmarked in misa_import_state and will be retried on the next run.
aws ec2 stop-instances --region "$REGION" --instance-ids "$INSTANCE_ID"
