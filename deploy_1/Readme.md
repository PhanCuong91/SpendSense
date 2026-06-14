ECR (Elastic Container Registry) -> EFS (Elastic File System)
EFS: use for SQLite Database
ECR:  need to upload container image
Pre-requiste:
Login:
aws configure

# 1. Get ECR login credentials
aws ecr get-login-password --region ap-southeast-1 | docker login --username AWS --password-stdin 359615771071.dkr.ecr.ap-southeast-1.amazonaws.com

# 2. Build the Docker image
docker build -t spendsense-app .

# 3. Tag the image for ECR
docker tag spend_sense:1.0.3 359615771071.dkr.ecr.ap-southeast-1.amazonaws.com/spend_sense:1.0.3
# 4. Create repo
aws ecr create-repository --repository-name spend_sense --region ap-southeast-1

# 4. Push to ECR
docker push 359615771071.dkr.ecr.ap-southeast-1.amazonaws.com/spend_sense:1.0.3


What actually runs containers in your terraform:

aws_ecs_task_definition.app_task describes the container image, secrets, mount (EFS) and environment.
aws_ecs_service.app_service is the runtime controller that keeps tasks running for that task definition.
aws_appautoscaling_target + aws_appautoscaling_scheduled_action are the scheduler: the scheduled action sets the ECS service desired count to 1 at your start cron and to 0 at stop cron → ECS will start/stop Fargate tasks accordingly. If enable_schedule = false the service is created at desired_count = 1 and runs all the time.

Debug:
- ECS task:
    1. Stopped status -> ResourceInitializationError: unable to pull secrets or registry auth: unable to retrieve secret from asm: There is a connection issue between the task and AWS Secrets Manager. Check your task network configuration. failed to fetch secret arn:aws:secretsmanager:ap-southeast-1:359615771071:secret:spendsense_gmail_credentials_json-ydLG7Q from secrets manager: operation error Secrets Manager: GetSecretValue, https response error StatusCode: 0, RequestID: , canceled, context deadline exceeded
    - Solution: # allow tasks to talk to endpoints on TLS
        resource "aws_security_group_rule" "ecs_allow_tls_self" {
        type                     = "ingress"
        from_port                = 443
        to_port                  = 443
        protocol                 = "tcp"
        security_group_id        = aws_security_group.ecs_sg.id
        source_security_group_id = aws_security_group.ecs_sg.id
        }

        # Interface endpoint for Secrets Manager
        resource "aws_vpc_endpoint" "secretsmanager" {
        vpc_id            = var.vpc_id
        service_name      = "com.amazonaws.${var.aws_region}.secretsmanager"
        vpc_endpoint_type = "Interface"
        subnet_ids        = var.private_subnet_ids
        security_group_ids = [aws_security_group.ecs_sg.id]
        private_dns_enabled = true
        tags = local.common_tags
        }

        # Interface endpoint for KMS (needed if secret is KMS-encrypted)
        resource "aws_vpc_endpoint" "kms" {
        vpc_id            = var.vpc_id
        service_name      = "com.amazonaws.${var.aws_region}.kms"
        vpc_endpoint_type = "Interface"
        subnet_ids        = var.private_subnet_ids
        security_group_ids = [aws_security_group.ecs_sg.id]
        private_dns_enabled = true
        tags = local.common_tags
        }

        AWS:
        - Secretmanager:
        resource "aws_secretsmanager_secret" "gmail_credentials" {
        name = "${var.project_name}_gmail_credentials_json"
        tags = local.common_tags
        }

        resource "aws_secretsmanager_secret_version" "gmail_credentials_version" {
        secret_id     = aws_secretsmanager_secret.gmail_credentials.id
        secret_string = file(var.gmail_credentials_file)
        }
    2. Issues: ResourceInitializationError: unable to pull secrets or registry auth: The task cannot pull registry auth from Amazon ECR: There is a connection issue between the task and Amazon ECR. Check your task network configuration. operation error ECR: GetAuthorizationToken, exceeded maximum number of attempts, 3, https response error StatusCode: 0, RequestID: , request send failed, Post "https://api.ecr.ap-southeast-1.amazonaws.com/": dial tcp 13.251.117.186:443: i/o timeout
    - Solution:
    # allow tasks to talk to endpoints on TLS
    resource "aws_security_group_rule" "ecs_allow_tls_self" {
    type                     = "ingress"
    from_port                = 443
    to_port                  = 443
    protocol                 = "tcp"
    security_group_id        = aws_security_group.ecs_sg.id
    source_security_group_id = aws_security_group.ecs_sg.id
    }

    # Interface endpoint for Secrets Manager
    resource "aws_vpc_endpoint" "secretsmanager" {
    vpc_id            = var.vpc_id
    service_name      = "com.amazonaws.${var.aws_region}.secretsmanager"
    vpc_endpoint_type = "Interface"
    subnet_ids        = var.private_subnet_ids
    security_group_ids = [aws_security_group.ecs_sg.id]
    private_dns_enabled = true
    tags = local.common_tags
    }

    # Interface endpoint for KMS (needed if secret is KMS-encrypted)
    resource "aws_vpc_endpoint" "kms" {
    vpc_id            = var.vpc_id
    service_name      = "com.amazonaws.${var.aws_region}.kms"
    vpc_endpoint_type = "Interface"
    subnet_ids        = var.private_subnet_ids
    security_group_ids = [aws_security_group.ecs_sg.id]
    private_dns_enabled = true
    tags = local.common_tags
    }
    3. Some secret cannot be deleted due to period:
    solution: restore and import:
    - aws secretsmanager restore-secret --secret-id  spendsense_gmail_credentials_json  --region ap-southeast-1
    - aws secretsmanager restore-secret --secret-id spendsense_gmail_token_json  --region ap-southeast-1
    - terraform import aws_secretsmanager_secret.gmail_token arn:aws:secretsmanager:ap-southeast-1:359615771071:secret:spendsense_gmail_token_json-ty4Xi1
    - terraform import aws_secretsmanager_secret.gmail_credentials arn:aws:secretsmanager:ap-southeast-1:359615771071:secret:spendsense_gmail_credentials_json-ydLG7Q
    4. CannotPullContainerError: pull image manifest has been retried 7 time(s): failed to resolve ref 359615771071.dkr.ecr.ap-southeast-1.amazonaws.com/spendsense-app:latest: 359615771071.dkr.ecr.ap-southeast-1.amazonaws.com/spendsense-app:latest: not found
    solution: terraform import aws_ecr_repository.app spend_sense - Configure again ECR repo that we update last time.
    5. CannotPullContainerError: pull image manifest has been retried 7 time(s): image Manifest does not contain descriptor matching platform 'linux/amd64'
    Solution: docker build --platform linux/amd64 -t spend_sense:1.0.4 .
    Rebuild new image run with linux/amd64, then upload to ECR
    6. ResourceInitializationError: failed to validate logger args: The task cannot find the Amazon CloudWatch log group defined in the task definition. There is a connection issue between the task and Amazon CloudWatch. Check your network configuration. : signal: killed
    Solution: 
    resource "aws_vpc_endpoint" "logs" {
    vpc_id            = var.vpc_id
    service_name      = "com.amazonaws.${var.aws_region}.logs"
    vpc_endpoint_type = "Interface"
    subnet_ids        = var.private_subnet_ids
    security_group_ids = [aws_security_group.ecs_sg.id]
    private_dns_enabled = true
    tags = local.common_tags
    }
    7. CannotPullContainerError: The task cannot pull 359615771071.dkr.ecr.ap-southeast-1.amazonaws.com/spend_sense:1.0.4@sha256:88e87b4d1cc2ffaf5cf4b6688cccc0d80f16e88e965468d68b917b27433cadb6 from the registry 359615771071.dkr.ecr.ap-southeast-1.amazonaws.com/spend_sense:1.0.4@sha256:88e87b4d1cc2ffaf5cf4b6688cccc0d80f16e88e965468d68b917b27433cadb6. There is a connection issue between the task and the registry. Check your task network configuration. : failed to copy: httpReadSeeker: failed open: failed to do request: Get 359615771071.dkr.ecr.ap-southeast-1.amazonaws.com/spend_sense:1.0.4@sha256:88e87b4d1cc2ffaf5cf4b6688cccc0d80f16e88e965468d68b917b27433cadb6: dial tcp 3.5.149.131:443: i/o timeout
    Solution: Your subnet subnet-055480c6716bfb03a is on a route table with an Internet Gateway, so it is effectively a public subnet. With assign_public_ip = false, Fargate tasks had no public IP and therefore could not reach ECR over the internet.
    assign_public_ip = true; resource "aws_ecs_service" "app_service" 

ECR running issue:
log:
  June 9, 2026, 22:28
  File "<frozen runpy>", line 198, in _run_module_as_main
  File "<frozen runpy>", line 88, in _run_code
  File "/app/app/workers/poller_worker.py", line 2, in <module>
  from app.gmail.poller import GmailPoller
  File "/app/app/gmail/poller.py", line 4, in <module>
  from app.db.session import SessionLocal
  File "/app/app/db/session.py", line 6, in <module>
  is_sqlite = make_url(settings.DATABASE_URL).get_backend_name() == "sqlite"
  ~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.13/site-packages/sqlalchemy/engine/url.py", line 856, in make_url
  return _parse_url(name_or_url)
  File "/usr/local/lib/python3.13/site-packages/sqlalchemy/engine/url.py", line 922, in _parse_url
  raise exc.ArgumentError(
  "Could not parse SQLAlchemy URL from given URL string"
  )
  sqlalchemy.exc.ArgumentError: Could not parse SQLAlchemy URL from given URL string
  Traceback (most recent call last):
  Solution: need 'sqlite:///'
  variable "db_file_path" {
    description = "Path inside the container where SQLite database file is stored."
    type        = string
    default     = "sqlite:///./data/txdb.sqlite3"
  }

  Traceback (most recent call last):
    File "<frozen runpy>", line 198, in _run_module_as_main
    File "<frozen runpy>", line 88, in _run_code
    File "/app/app/workers/poller_worker.py", line 21, in <module>
      main()
      ~~~~^^
    File "/app/app/workers/poller_worker.py", line 10, in main
      poller = GmailPoller()
    File "/app/app/gmail/poller.py", line 18, in __init__
      self.client = GmailClient()
                    ~~~~~~~~~~~^^
    File "/app/app/gmail/client.py", line 15, in __init__
      creds = load_credentials()
    File "/app/app/gmail/auth.py", line 26, in load_credentials
      flow = InstalledAppFlow.from_client_secrets_file(
          settings.GMAIL_CREDENTIALS_PATH, SCOPES
      )
    File "/usr/local/lib/python3.13/site-packages/google_auth_oauthlib/flow.py", line 198, in from_client_secrets_file
      with open(client_secrets_file, "r") as json_file:
            ~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^
  FileNotFoundError: [Errno 2] No such file or directory: '{"installed":{"client_id":"115772520499-ejm9mfgv79bi7kjnh4rjql9est8ilbhl.apps.googleusercontent.com","project_id":"arched-market-488902-h5","auth_uri":"https://accounts.google.com/o/oauth2/auth","token_uri":"https://oauth2.googleapis.com/token","auth_provider_x509_cert_url":"https://www.googleapis.com/oauth2/v1/certs","client_secret":"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","redirect_uris":["http://localhost"]}}\n'
  solution: Local work with file path, but container run on cloud use string


- Link secrets and volume to container:
resource "aws_ecs_task_definition" "app_task" {
  family                   = "${var.project_name}-task"
  cpu                      = var.task_cpu
  memory                   = var.task_memory
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  execution_role_arn       = aws_iam_role.ecs_task_execution_role.arn
  task_role_arn            = aws_iam_role.ecs_task_role.arn

  volume {
    name = "efs-data"

    efs_volume_configuration {
      file_system_id          = aws_efs_file_system.app_fs.id
      authorization_config {
        access_point_id = aws_efs_access_point.app_ap.id
        iam             = "DISABLED"
      }
      root_directory       = var.efs_root_path
      transit_encryption   = "ENABLED"
    }
  }

  container_definitions = jsonencode([
    {
      name      = var.app_container_name
      image     = "${aws_ecr_repository.app.repository_url}:${var.app_image_tag}"
      essential = true

      environment = [
        {
          name  = "DB_PATH"
          value = "${var.db_file_path}"
        }
      ]

      secrets = [
        {
          name      = "GMAIL_CREDENTIALS_JSON"
          valueFrom = aws_secretsmanager_secret.gmail_credentials.arn
        },
        {
          name      = "GMAIL_TOKEN_JSON"
          valueFrom = aws_secretsmanager_secret.gmail_token.arn
        }
      ]

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.ecs_logs.name
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = var.project_name
        }
      }

      mountPoints = [
        {
          sourceVolume  = "efs-data"
          containerPath = var.db_mount_path
          readOnly      = false
        }
      ]
    }
  ])
} 


Download EFS to local Mac:

1) Get the EFS filesystem ID
  cd /Users/cuongphan/Downloads/DevOps/SpendSense/deploy_1
  terraform output -raw efs_file_system_id
  aws efs describe-file-systems --region ap-southeast-1 --query 'FileSystems[?Tags[?Key==`Project` && Value==`spendsense`]].FileSystemId' --output text
fs-05f11f02c3a0e4420

2) Get the EFS access point ID
This is useful because your task mounts via an EFS access point:
  EFS_ID=$(terraform output -raw efs_file_system_id)
  aws efs describe-access-points --file-system-id "$EFS_ID" --region ap-southeast-1 --query 'AccessPoints[0].AccessPointId' --output text
fsap-095f4730bbd109600

3) Mount EFS on a host in the same VPC/subnet
Use an EC2 instance in the same VPC/subnet (or an existing instance already attached to that VPC). Install the EFS client and mount:
  # on the EC2 host
  sudo yum install -y amazon-efs-utils   # Amazon Linux
  sudo mkdir -p /mnt/efs
  sudo mount -t efs -o tls,accesspoint=fsap-0276db2462bea38f8 fs-081d1bf7f88a9c2a5 fs-081d1bf7f88a9c2a5.efs.ap-southeast-1.amazonaws.com:/ /mnt/efs

  sudo mount -t efs -o tls,accesspoint=fsap-0276db2462bea38f8 fs-081d1bf7f88a9c2a5:/ /mnt/efs

  sudo mount -t efs -o tls,accesspoint=fsap-0276db2462bea38f8 fs-081d1bf7f88a9c2a5:/ /mnt/efs
  
4) Copy the DB file
On that host:
  ls /mnt/efs
  # If the access point root is /spendsense, the file should appear here:
  ls /mnt/efs/txdb.sqlite3

  # copy it locally on the host
  cp /mnt/efs/txdb.sqlite3 /home/ec2-user/


Create EC2 in same VPC
1. Get a current Amazon Linux AMI for region:
  AMI_ID=$(aws ssm get-parameter --name /aws/service/ami-amazon-linux-latest/amzn2-ami-hvm-x86_64-gp2 --region ap-southeast-1 --query 'Parameter.Value' --output text)
  echo "$AMI_ID"
ami-0df749f12c31d3cd6
2. Create an EC2 security group in the same VPC:
  SG_ID=$(aws ec2 create-security-group \
  --group-name spendsense-ec2-sg \
  --description "EC2 for EFS access" \
  --vpc-id vpc-0e67ef7841be38480 \
  --region ap-southeast-1 \
  --query 'GroupId' --output text)
sg-0e26ed800b1e9fbbd

  EC2_SG_ID=$(aws ec2 describe-instances \
    --filters "Name=tag:Name,Values=spendsense-efs-access" "Name=instance-state-name,Values=running" \
    --region ap-southeast-1 \
    --query 'Reservations[].Instances[].SecurityGroups[].GroupId' \
    --output text)

  EFS_SG_ID=$(aws ec2 describe-security-groups \
  --filters "Name=group-name,Values=spendsense-efs-sg" \
  --region ap-southeast-1 \
  --query 'SecurityGroups[0].GroupId' --output text)

3. Allow SSH from your IP:
  MY_IP=$(curl -s https://checkip.amazonaws.com)/32
  58.182.62.68/32
  aws ec2 authorize-security-group-ingress \
    --group-id "$EFS_SG_ID" \
    --protocol tcp --port 22 \
    --cidr "$MY_IP" \
    --source-group "$EC2_SG_ID" \
    --region ap-southeast-1

4. Launch the EC2 instance in the same subnet:
  aws ec2 run-instances \
    --image-id "$AMI_ID" \
    --instance-type t3.micro \
    --key-name ap-southeast-1 \
    --subnet-id subnet-055480c6716bfb03a \
    --security-group-ids "$SG_ID" \
    --associate-public-ip-address \
    --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=spendsense-efs-access}]' \
    --region ap-southeast-1

  aws ec2 run-instances \
    --image-id "$AMI_ID" \
    --instance-type t3.micro \
    --key-name ap-southeast-1 \
    --subnet-id subnet-055480c6716bfb03a \
    --security-group-ids "$EFS_SG_ID" \
    --associate-public-ip-address \
    --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=spendsense-efs-access}]' \
    --region ap-southeast-1

  run again this:
  aws ec2 authorize-security-group-ingress \
  --group-id sg-026062d55a918cb78 \
  --protocol tcp \
  --port 2049 \
  --source-group sg-026062d55a918cb78 \
  --region ap-southeast-1
  to add a self-referential NFS rull

ssh -v -i "/Volumes/Macintosh HD/Users/cuongphan/Downloads/ap-southeast-1.pem" ec2-user@$UBLIC_IP

Error:
1. b'mount.nfs4: Connection reset by peer'
  solution:
2. [ERROR]: An error occurred (InvalidPermission.Duplicate) when calling the AuthorizeSecurityGroupIngress operation: the specified rule "peer: 58.182.62.68/32, TCP, from port: 22, to port: 22, ALLOW" already exists
  Solution:

scp -i "/Volumes/Macintosh HD/Users/cuongphan/Downloads/ap-southeast-1.pem"   "/Volumes/Macintosh HD/Users/cuongphan/Downloads/DevOps/SpendSense/data/txdb.sqlite3" ec2-user@13.228.21.86:/mnt/efs
