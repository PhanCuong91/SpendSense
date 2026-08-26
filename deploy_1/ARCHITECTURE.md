# Deploy_1 Terraform Architecture

> File: [deploy_1/main.tf](deploy_1/main.tf)  
> Region: `ap-southeast-1` (configurable via `var.aws_region`)  
> Goal: Run the SpendSense Gmail poller + correlator on AWS Fargate for ~15 minutes per day, with SQLite persisted on EFS and backed up to S3.

---

## 1. Resource Overview

```plantuml
@startuml Deploy1_ResourceOverview
!theme plain
skinparam componentStyle rectangle
skinparam linetype ortho
skinparam packageBackgroundColor<<registry>> #FFE4E1
skinparam packageBackgroundColor<<secrets>> #E6E6FA
skinparam packageBackgroundColor<<storage>> #E0FFFF
skinparam packageBackgroundColor<<iam>> #FFF8DC
skinparam packageBackgroundColor<<network>> #F0FFF0
skinparam packageBackgroundColor<<compute>> #E1F5FE
skinparam packageBackgroundColor<<scheduling>> #FFFACD
skinparam packageBackgroundColor<<backup>> #F5F5DC
skinparam packageBackgroundColor<<logging>> #DCDCDC

skinparam component<<registry>> {
    BackgroundColor #FF6B6B
    FontColor white
}
skinparam component<<secrets>> {
    BackgroundColor #9370DB
    FontColor white
}
skinparam component<<storage>> {
    BackgroundColor #00CED1
    FontColor white
}
skinparam component<<iam>> {
    BackgroundColor #DAA520
    FontColor black
}
skinparam component<<network>> {
    BackgroundColor #32CD32
    FontColor white
}
skinparam component<<compute>> {
    BackgroundColor #1E90FF
    FontColor white
}
skinparam component<<scheduling>> {
    BackgroundColor #FFD700
    FontColor black
}
skinparam component<<backup>> {
    BackgroundColor #BDB76B
    FontColor black
}
skinparam component<<logging>> {
    BackgroundColor #808080
    FontColor white
}

skinparam database<<storage>> {
    BackgroundColor #00BFFF
    FontColor white
}

package "Container Registry" <<registry>> {
    [aws_ecr_repository\napp] as ECR <<registry>>
}

package "Secrets" <<secrets>> {
    [aws_secretsmanager_secret\ngmail_credentials] as SEC_CREDS <<secrets>>
    [aws_secretsmanager_secret\ngmail_token] as SEC_TOKEN <<secrets>>
}

package "Shared Storage" <<storage>> {
    database "aws_efs_file_system\napp_fs" as EFS <<storage>>
    [aws_efs_access_point\napp_ap] as AP <<storage>>
    [aws_efs_mount_target] as MT <<storage>>
}

package "IAM" <<iam>> {
    [aws_iam_role\necs_task_execution_role] as EXEC <<iam>>
    [aws_iam_role\necs_task_role] as TASK <<iam>>
    [aws_iam_role\neventbridge_ecs_role] as EB_ROLE <<iam>>
}

package "Network / Security" <<network>> {
    [vpc_id from variables] as VPC <<network>>
    [aws_security_group\necs_sg] as SG_ECS <<network>>
    [aws_security_group\nefs_sg] as SG_EFS <<network>>
}

package "Compute" <<compute>> {
    [aws_ecs_cluster\napp_cluster] as CLUSTER <<compute>>
    [aws_ecs_task_definition\napp_task] as APP_TASK <<compute>>
    [aws_ecs_task_definition\nbackup_task] as BACKUP_TASK <<compute>>
    [aws_ecs_service\napp_service] as SERVICE <<compute>>
}

package "Scheduling" <<scheduling>> {
    [aws_appautoscaling_target] as ASG <<scheduling>>
    [aws_appautoscaling_scheduled_action\nstart_daily] as START <<scheduling>>
    [aws_appautoscaling_scheduled_action\nstop_daily] as STOP <<scheduling>>
}

package "Backup Trigger" <<backup>> {
    [aws_cloudwatch_event_rule\napp_task_stopped] as RULE <<backup>>
    [aws_cloudwatch_event_target\nrun_backup_task] as TARGET <<backup>>
}

package "Logging" <<logging>> {
    [aws_cloudwatch_log_group\necs_logs] as CW <<logging>>
}

ECR --> APP_TASK #Crimson
ECR --> BACKUP_TASK #Crimson
SEC_CREDS --> APP_TASK #DarkViolet
SEC_TOKEN --> APP_TASK #DarkViolet

EFS --> AP #DeepSkyBlue
AP --> APP_TASK #DeepSkyBlue
AP --> BACKUP_TASK #DeepSkyBlue
MT --> EFS #DeepSkyBlue

EXEC --> APP_TASK #DarkGoldenRod
EXEC --> BACKUP_TASK #DarkGoldenRod
TASK --> APP_TASK #DarkGoldenRod
TASK --> BACKUP_TASK #DarkGoldenRod
EB_ROLE --> TARGET #DarkGoldenRod

SG_ECS --> SERVICE #ForestGreen
SG_EFS --> EFS #ForestGreen

APP_TASK --> SERVICE #DodgerBlue
BACKUP_TASK --> TARGET #DodgerBlue

CLUSTER --> SERVICE #DodgerBlue
SERVICE --> ASG #Gold
ASG --> START #Gold
ASG --> STOP #Gold

SERVICE --> RULE #DarkKhaki
RULE --> TARGET #DarkKhaki
TARGET --> CLUSTER #DarkKhaki

APP_TASK --> CW #DimGray
BACKUP_TASK --> CW #DimGray

@enduml
```

---

## 2. Data Flow During a Daily Run

```plantuml
@startuml Deploy1_DailyRunSequence
!theme plain
skinparam sequenceArrowThickness 2
skinparam participantBackgroundColor<<scheduler>> #FFD700
skinparam participantBackgroundColor<<scaling>> #FFA500
skinparam participantBackgroundColor<<ecs>> #87CEEB
skinparam participantBackgroundColor<<storage>> #00CED1
skinparam participantBackgroundColor<<s3>> #4682B4
skinparam participantBackgroundColor<<external>> #90EE90
skinparam participantBackgroundColor<<backup>> #BDB76B
skinparam participantFontColor<<scheduler>> black
skinparam participantFontColor<<scaling>> black
skinparam participantFontColor<<ecs>> black
skinparam participantFontColor<<storage>> white
skinparam participantFontColor<<s3>> white
skinparam participantFontColor<<external>> black
skinparam participantFontColor<<backup>> black

actor Scheduler as "EventBridge\nSchedule" <<scheduler>>
participant AS as "Application\nAuto Scaling" <<scaling>>
participant Svc as "ECS Service" <<ecs>>
participant Task as "ECS Task\n(app_task)" <<ecs>>
participant EFS as "EFS Volume" <<storage>>
participant S3 as "S3 Backup\nBucket" <<s3>>
participant Gmail as "Gmail API" <<external>>
participant EB as "EventBridge" <<scheduler>>
participant Backup as "Backup Task" <<backup>>

Scheduler -> AS: start_daily\nset desired_count = 1 #Gold
AS -> Svc: update desired_count #DarkOrange
Svc -> Task: launch app_task (Fargate) #SteelBlue

Task -> EFS: mount /app/data #DeepSkyBlue
alt DB missing on EFS #LightBlue
    Task -> S3: download txdb.sqlite3 #SteelBlue
    S3 --> Task: restore DB #SteelBlue
else DB exists #LightBlue
    Task -> Task: use existing DB #Gray
end

Task -> Gmail: poll for bank emails #ForestGreen
Gmail --> Task: messages #ForestGreen
Task -> EFS: store raw emails + parsed candidates #DeepSkyBlue
Task -> Task: run correlator worker #SteelBlue
Task -> EFS: update events/correlation links #DeepSkyBlue

Scheduler -> AS: stop_daily\nset desired_count = 0 #Gold
AS -> Svc: update desired_count #DarkOrange
Svc -> Task: stop task #SteelBlue

Task --> EB: ECS Task State Change STOPPED #Crimson
EB -> Backup: run backup_task #DarkKhaki
Backup -> EFS: mount /app/data #DeepSkyBlue
Backup -> S3: aws s3 cp txdb.sqlite3 #SteelBlue
S3 --> Backup: uploaded #SteelBlue

@enduml
```

---

## 3. Resource Details

### 3.1 Container Registry

| Resource | Purpose |
|----------|---------|
| `aws_ecr_repository.app` | Stores the `spend_sense` Docker image. Scan on push enabled. |

### 3.2 Secrets

| Resource | Purpose |
|----------|---------|
| `aws_secretsmanager_secret.gmail_credentials` | Holds `credentials.json` for Gmail OAuth. |
| `aws_secretsmanager_secret.gmail_token` | Holds `token.json` for Gmail OAuth. |

These are injected into the ECS task container as environment variables `GMAIL_CREDENTIALS_JSON` and `GMAIL_TOKEN_JSON`.

### 3.3 Shared Storage

| Resource | Purpose |
|----------|---------|
| `aws_efs_file_system.app_fs` | Managed NFS for persisting SQLite across task runs. |
| `aws_efs_mount_target.mt` | Mounts EFS into the subnets used by ECS tasks. |
| `aws_efs_access_point.app_ap` | Access point at `/spendsense` with POSIX user UID/GID 1000. |

The SQLite file lives on EFS and is mounted into the container at `/app/data`.

### 3.4 IAM Roles

| Resource | Purpose |
|----------|---------|
| `aws_iam_role.ecs_task_execution_role` | Allows Fargate to pull images, write logs, and read Secrets Manager. |
| `aws_iam_role.ecs_task_role` | Allows the running container to access S3 backup bucket. |
| `aws_iam_role.eventbridge_ecs_role` | Allows EventBridge to run the backup ECS task. |

### 3.5 Network / Security

| Resource | Purpose |
|----------|---------|
| `aws_security_group.ecs_sg` | Allows all outbound traffic from ECS tasks. |
| `aws_security_group.efs_sg` | Allows inbound NFS (port 2049) only from `ecs_sg`. |

### 3.6 ECS Compute

| Resource | Purpose |
|----------|---------|
| `aws_ecs_cluster.app_cluster` | Logical cluster for all Fargate tasks. |
| `aws_ecs_task_definition.app_task` | Main task: runs the poller worker. Mounts EFS, restores DB from S3 if missing. |
| `aws_ecs_task_definition.backup_task` | One-off task: uploads `txdb.sqlite3` from EFS to S3. |
| `aws_ecs_service.app_service` | ECS service running `app_task`. Desired count is controlled by scheduled scaling. |

### 3.7 Scheduling

| Resource | Purpose |
|----------|---------|
| `aws_appautoscaling_target.ecs_service_target` | Tracks the ECS service as a scalable target. Min=0, Max=1. |
| `aws_appautoscaling_scheduled_action.start_daily` | Sets desired count to 1 at scheduled time. |
| `aws_appautoscaling_scheduled_action.stop_daily` | Sets desired count to 0 at scheduled time. |

### 3.8 Backup Trigger

| Resource | Purpose |
|----------|---------|
| `aws_cloudwatch_event_rule.app_task_stopped` | Listens for ECS task STOPPED events for this service. |
| `aws_cloudwatch_event_target.run_backup_task` | Triggers the backup task when the main task stops. |

### 3.9 Logging

| Resource | Purpose |
|----------|---------|
| `aws_cloudwatch_log_group.ecs_logs` | Collects logs from all containers. 14-day retention. |

---

## 4. Daily Lifecycle

```plantuml
@startuml Deploy1_DailyLifecycle
!theme plain
skinparam backgroundColor #FEFEFE
skinparam activityBackgroundColor #E1F5FE
skinparam activityBorderColor #0288D1
skinparam activityFontColor #01579B
skinparam startColor #4CAF50
skinparam endColor #F44336
skinparam arrowColor #0288D1
skinparam arrowThickness 2

start
#FFD700:Scheduled Start;
#FFF59D:Set desired_count = 1;
#E1F5FE:ECS runs app_task;
#B2EBF2:Restore DB from S3 if needed;
#C8E6C9:Poll Gmail + parse emails;
#C8E6C9:Run correlator worker;
#B2EBF2:Write SQLite to EFS;
#FFCC80:Scheduled Stop;
#FFF59D:Set desired_count = 0;
#E1F5FE:ECS stops app_task;
#FFF9C4:EventBridge triggers backup_task;
#B2EBF2:Upload SQLite to S3;
#F5F5F5:Wait until next day;
stop

@enduml
```

---

## 5. Known Gaps

1. **Task command is wrong**: `app_task` runs `python -m app.workers.poller_worker --host 0.0.0.0 --port 8000`. The poller worker does not accept host/port arguments.
2. **Only one container role**: the task definition runs the poller only. If you also want the correlator to run, it must be added as another container or run in the same process.
3. **No API**: there is no FastAPI container in this deployment.
4. **No container health check**: ECS only knows if the process exited.
5. **Public IP**: tasks get public IPs because they need outbound internet for ECR, Secrets Manager, Gmail, and S3.

For a 15-minute daily run, these gaps are acceptable except for #1, which prevents the task from starting correctly.
