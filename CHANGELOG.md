# Changelog — SpendSense

All notable changes to this project are documented here.

Format based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [Unreleased]

### Added
- Full project documentation: `docs/ARCHITECTURE.md`, `docs/WORKERS.md`, `docs/CONFIGURATION.md`, `docs/DEVELOPMENT.md`, `docs/CICD.md`, `docs/DEPLOYMENT.md`
- GitHub PR template: `.github/pull_request_template.md`
- Rewrote `README.md` to reflect actual stack (Python + SQLite + Docker + Gmail + MISA)

---

## [0.1.0] — Initial Release

### Features
- **poller_worker**: Polls Gmail API for bank transaction emails (ACB, DBS, PayLah, TrustBank)
- **parser_worker**: Parses email bodies into structured transaction candidates (inline, called by poller)
- **correlator_worker**: Matches debit/credit pairs from inter-bank transfers
- **misa.runner**: Imports parsed transactions into MISA Money Keeper via Playwright browser automation
- SQLite persistence via SQLAlchemy ORM
- Alembic database migrations
- Single Docker image with `APP_ROLE` env-var role switching (`poller` | `correlator` | `misa`)
- GitHub Actions label-based CI/CD pipeline (`check` label → test, `merge` label → test + auto-merge + AWS deploy)
- Terraform infrastructure on AWS (ECR, ECS, Secrets Manager, SSM, S3 remote state)

### Supported Banks
- ACB Vietnam (`mailalert@acb.com.vn`)
- DBS iBanking Singapore (`ibanking.alert@dbs.com`)
- PayLah Singapore (`paylah.alert@dbs.com`)
- TrustBank Singapore (`from_us@trustbank.sg`)
