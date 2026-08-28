# AWS Cost Comparison — SpendSense Deployment Options

> Region: `ap-southeast-1` (Singapore)  
> Assumptions: app runs ~15 minutes per day, SQLite database (~10-100 MB), low email volume.

All prices are approximate public on-demand rates as of 2026-08-08. Use the [AWS Pricing Calculator](https://calculator.aws/) for exact quotes.

---

## 1. Architecture Options Compared

| Option | Compute | Storage | Network | Pros | Cons | Estimated Monthly Cost |
|--------|---------|---------|---------|------|------|------------------------|
| **A1. Current design (Fargate poller + EC2 MISA, download Chromium)** | Fargate 0.5 vCPU / 1 GB for 15 min/day; t3.micro EC2 for ~20 min/day | EFS + S3 | Public IP only | Cheapest overall; matches your workflow | Must manage EC2 start/stop; 1-2 min Chromium download | **~$1.65/month** |
| A2. Same as A1 but persist Chromium on EBS | Same compute | EFS + S3 + EBS | Public IP only | Faster EC2 startup | EBS cost even when stopped | **~$2.40/month** |
| **B. Fargate only (headless MISA)** | Fargate 1 vCPU / 2 GB for ~30 min/day | EFS + S3 | Public IP only | No EC2 to manage | Headless MISA is risky; may fail login | **~$10-15/month** if it works |
| **C. EC2 for everything** | One t3.micro running 15-30 min/day | EBS + S3 | Public IP | Simple single node | Less reliable scheduled start/stop; EBS cost | **~$10-16/month** |
| **D. Fargate + RDS PostgreSQL** | Fargate 0.5 vCPU / 1 GB for 15 min/day | RDS db.t4g.micro + EFS/S3 | Public IP or NAT GW | Proper managed DB | RDS alone is ~$15/month; overkill | **~$30-45/month** |
| **E. Fargate + NAT Gateway** | Fargate 0.5 vCPU / 1 GB for 15 min/day | EFS + S3 | NAT Gateway | Private subnets, no public IP on tasks | NAT Gateway ~$32/month; not worth it | **~$45-55/month** |

**Recommended: Option A1** — current design direction, with Fargate for ingestion, EC2 for MISA import, and Chromium downloaded at runtime.

---

## 2. Option A Detailed Breakdown

### 2.1 Compute

| Service | Usage | Unit Price | Monthly Cost |
|---------|-------|------------|--------------|
| **ECS Fargate** | 0.5 vCPU + 1 GB RAM, 15 min/day | $0.02456/vCPU-hr + $0.00271/GB-hr | ~$0.20/month |
| **EC2 t3.micro** | ~20 min/day (MISA import), started on demand | $0.0104/hr on-demand | ~$0.10/month |
| **Fargate backup task** | 0.5 vCPU + 1 GB RAM, ~2 min/day | Same as above | ~$0.03/month |

**Compute subtotal: ~$0.33/month**

### 2.2 EC2 MISA Import Options

There are two ways to handle Playwright Chromium on the EC2 instance:

| Approach | How it works | Monthly Cost |
|----------|--------------|--------------|
| **A1. Download Chromium every run** | Container runs `playwright install chromium` at startup | ~$0.10/month (compute) + data transfer is negligible |
| **A2. Persist Chromium on EBS** | Install Chromium once on EBS, mount into container | ~$0.72/month (8 GB gp3 EBS) + ~$0.05/month compute |

**A1 is cheaper** because it avoids EBS cost. The download is ~150-200 MB and takes 1-2 minutes, which is acceptable for a daily job.

### 2.3 Storage

| Service | Usage | Unit Price | Monthly Cost |
|---------|-------|------------|--------------|
| **EFS Standard** | 1 GB stored, accessed 15 min/day | $0.30/GB-month | ~$0.30/month |
| **EFS Infrequent Access** | Same data moved to IA after 7 days | $0.025/GB-month | ~$0.03/month |
| **S3 Standard** | 100 MB backup, 30 PUT/GET per month | $0.025/GB + $0.005/1k requests | ~$0.01/month |
| **ECR** | 100 MB image (no browsers), 30 pulls/month | $0.10/GB-month + $0.09/GB pull | ~$0.05/month |
| **EBS (optional)** | Only if using A2 (persist Chromium) | $0.09/GB-month for gp3 | ~$0.72/month |

**Storage subtotal: ~$0.40/month (A1) or ~$1.10/month (A2)**

### 2.4 Networking

| Service | Usage | Unit Price | Monthly Cost |
|---------|-------|------------|--------------|
| **Public IPv4** | Assigned to Fargate tasks + EC2 | $0.005/hr per IP | ~$0.10/month (only when running) |
| **Data transfer out** | Minimal (Gmail API, MISA web, Chromium download) | Usually free or negligible | ~$0.00/month |

**Networking subtotal: ~$0.10/month**

### 2.5 Other

| Service | Usage | Unit Price | Monthly Cost |
|---------|-------|------------|--------------|
| **CloudWatch Logs** | ~10 MB logs/month | $0.50/GB ingested | ~$0.01/month |
| **Secrets Manager** | 2 secrets | $0.40/secret/month | $0.80/month |
| **EventBridge** | 2 scheduled rules + S3 events | $1.00/million events | ~$0.00/month |

**Other subtotal: ~$0.81/month**

### 2.6 Option A Total

| Category | A1: Download Chromium | A2: EBS Persist |
|----------|----------------------|-----------------|
| Compute | ~$0.33 | ~$0.38 |
| Storage | ~$0.40 | ~$1.10 |
| Networking | ~$0.10 | ~$0.10 |
| Other | ~$0.81 | ~$0.81 |
| **Total** | **~$1.65/month** | **~$2.40/month** |

> With spot pricing for EC2 or Fargate Spot, A1 could drop to **~$1.10/month**.

---

## 3. Why Other Options Cost More

### Option B — Fargate only (headless MISA)

Fargate 1 vCPU / 2 GB for ~30 min/day:
- Compute: ~$0.60/month
- Storage: ~$0.50/month
- Other: ~$0.81/month
- **Total: ~$1.90/month**

Only slightly more expensive, but **not recommended** because headless Chromium may fail MISA login or 2FA.

### Option C — EC2 for everything

One t3.micro running 30 min/day:
- EC2 compute: ~$0.16/month
- EBS gp3 8 GB: ~$0.72/month (EBS is charged while stopped)
- Public IP while running: ~$0.08/month
- S3/ECR/Logs/Secrets: ~$0.95/month
- **Total: ~$1.90/month**

More expensive than Option A1 because EBS persists while the instance is stopped.

### Option D — Fargate + RDS PostgreSQL

RDS db.t4g.micro is the killer:
- RDS compute + storage: ~$15/month
- Fargate: ~$0.20/month
- Other: ~$0.95/month
- **Total: ~$16/month**

Overkill for a personal project.

### Option E — Fargate + NAT Gateway

NAT Gateway is the killer:
- NAT Gateway hourly: ~$32/month
- Fargate: ~$0.20/month
- Other: ~$0.95/month
- **Total: ~$33/month**

Not justified for a task that only needs outbound internet for 15 minutes/day.

---

## 4. Cost-Saving Tips

| Tip | Savings |
|-----|---------|
| Use **Fargate Spot** for ECS tasks | ~50-70% on Fargate compute |
| Use **EC2 Spot** for MISA runner | ~50-70% on EC2 compute |
| **Download Chromium at runtime** instead of EBS persistence | Saves ~$0.70/month EBS cost |
| Enable **EFS Lifecycle Management** to IA | ~90% on EFS storage after data ages |
| Keep **only latest backup** in S3 | Avoids S3 bloat |
| Add **ECR lifecycle policy** | Avoids old image storage |
| Do **not** install Chromium in Docker image | Keeps ECR image ~100 MB instead of ~1.5 GB |

---

## 5. Summary

| Option | Monthly Cost | Recommended? |
|--------|--------------|--------------|
| **A1. Fargate poller + EC2 MISA (download Chromium)** | **~$1.65** | **Yes** |
| A2. Fargate poller + EC2 MISA (EBS persist Chromium) | ~$2.40 | OK if you want faster startup |
| B. Fargate only (headless) | ~$1.90 | No — risky |
| C. EC2 for everything | ~$1.90 | No — EBS cost |
| D. Fargate + RDS | ~$16 | No — overkill |
| E. Fargate + NAT Gateway | ~$33 | No — wasteful |

**Go with Option A1** (download Chromium at runtime). It is the cheapest practical design that handles MISA's browser-based login correctly.
