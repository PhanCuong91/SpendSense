# SpendSense

A Python automation service that polls Gmail for bank transaction emails, parses and stores them in a local SQLite database, and imports them into [MISA Money Keeper](https://misa.com.vn) via browser automation.

---

## Overview

```
Gmail Inbox
    │  (Gmail API — bank emails only)
    ▼
poller_worker  ──► email_raw (SQLite)
    │
    ▼
parser_worker  ──► parsed_transaction_candidate (SQLite)
    │
    ▼
[optional] correlator_worker  ──► correlation_link (SQLite)
    │
    ▼
misa.runner  ──► MISA Money Keeper (via Playwright)
```

**Supported banks:**
| Bank | Country | Trigger email |
|------|---------|---------------|
| ACB | Vietnam | `mailalert@acb.com.vn` |
| DBS iBanking | Singapore | `ibanking.alert@dbs.com` |
| PayLah | Singapore | `paylah.alert@dbs.com` |
| TrustBank | Singapore | `from_us@trustbank.sg` |

---

## Quick Start

### Prerequisites
- Python 3.13
- Docker & Docker Compose
- A Google Cloud project with Gmail API enabled
- `credentials.json` and `token.json` from Gmail OAuth2 flow

### 1. Clone & configure

```bash
git clone <repo-url>
cd SpendSense
cp .env.example .env        # edit DATABASE_URL, GMAIL paths, etc.
cp .env.misa.example .env.misa  # edit MISA_USERNAME, MISA_PASSWORD
```

### 2. Run with Docker (recommended)

```bash
# Start poller worker (runs continuously)
docker compose up poller-worker

# Start correlator worker (optional)
docker compose up correlator-worker

# Run MISA import for a date range (batch job)
MISA_START_DATE=2024-01-01 MISA_END_DATE=2024-01-31 \
  docker compose --profile misa run --rm misa-runner
```

### 3. Run locally (without Docker)

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
playwright install chromium   # for misa.runner only

# Start the poller worker
python -m app.workers.poller_worker

# Run MISA import
python -m app.misa.runner --start-date 2024-01-01 --end-date 2024-01-31
```

---

## Project Structure

```
SpendSense/
├── app/
│   ├── workers/
│   │   ├── poller_worker.py        # Gmail → SQLite loop
│   │   ├── parser_worker.py        # Email → ParsedTransactionCandidate
│   │   └── correlator_worker.py    # Match debit/credit pairs (optional)
│   ├── misa/
│   │   ├── runner.py               # CLI batch job: SQLite → MISA
│   │   ├── client.py               # Playwright browser automation
│   │   ├── query.py                # Query candidates to import
│   │   ├── mapper.py               # Map candidates to MISA fields
│   │   └── dedup_store.py          # Prevent duplicate imports
│   ├── gmail/
│   │   ├── poller.py               # Gmail API polling logic
│   │   ├── client.py               # Gmail API wrapper
│   │   └── auth.py                 # OAuth2 auth
│   ├── db/
│   │   ├── models/                 # SQLAlchemy models
│   │   ├── session.py              # SQLite session factory
│   │   └── base.py                 # Declarative base
│   ├── parsing/                    # Email body parsers (per bank)
│   ├── classification/             # Transaction type classifier
│   ├── correlation/                # Debit/credit matching logic
│   └── core/
│       ├── config.py               # Settings (pydantic-settings)
│       └── logging.py              # Structured logging
├── tests/                          # pytest test suite
├── scripts/                        # Dev & MISA helper scripts
├── deploy_1/                       # Terraform — AWS infrastructure
├── .github/workflows/              # GitHub Actions CI/CD
├── docker-compose.yaml
├── Dockerfile
├── Makefile
└── requirements.txt
```

---

## Environment Variables

See [`docs/CONFIGURATION.md`](docs/CONFIGURATION.md) for the full reference.

Key variables:

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DATABASE_URL` | ✅ | — | SQLite path, e.g. `sqlite:////app/data/txdb.sqlite3` |
| `GMAIL_CREDENTIALS_JSON` | ✅* | — | OAuth2 credentials JSON (base64 or raw) |
| `GMAIL_TOKEN_JSON` | ✅* | — | OAuth2 token JSON |
| `POLL_INTERVAL_SECONDS` | ❌ | `300` | How often the poller runs (seconds) |
| `MISA_USERNAME` | ✅ for MISA | — | MISA login email (in `.env.misa`) |
| `MISA_PASSWORD` | ✅ for MISA | — | MISA login password (in `.env.misa`) |

*Can be file paths (`GMAIL_CREDENTIALS_PATH`, `GMAIL_TOKEN_PATH`) instead.

---

## Workers

See [`docs/WORKERS.md`](docs/WORKERS.md) for details.

| Worker | Mode | Description |
|--------|------|-------------|
| `poller_worker` | Continuous loop | Polls Gmail every 5 min, stores raw emails |
| `parser_worker` | Inline (called by poller) | Parses emails into transaction candidates |
| `correlator_worker` | Continuous loop | Matches debit/credit pairs (optional) |
| `misa.runner` | One-shot batch job | Imports candidates into MISA via Playwright |

---

## Running Tests

```bash
make test
# or
pytest -q --disable-warnings
```

---

## CI/CD

Label-based GitHub Actions pipeline. See [`docs/CICD.md`](docs/CICD.md).

| Label | Action |
|-------|--------|
| `check` | Run tests only |
| `merge` | Run tests → auto-merge → build ECR image → Terraform deploy to AWS |

---

## Documentation Index

| Doc | Description |
|-----|-------------|
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | System design & data flow |
| [`docs/WORKERS.md`](docs/WORKERS.md) | Worker reference |
| [`docs/CONFIGURATION.md`](docs/CONFIGURATION.md) | All env vars |
| [`docs/DEVELOPMENT.md`](docs/DEVELOPMENT.md) | Local dev setup |
| [`docs/CICD.md`](docs/CICD.md) | CI/CD pipeline |
| [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md) | AWS infrastructure & Terraform |
