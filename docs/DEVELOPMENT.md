# Development Guide — SpendSense

## Prerequisites

| Tool | Version | Install |
|------|---------|---------|
| Python | 3.13 | [python.org](https://python.org) |
| Docker | 24+ | [docker.com](https://docker.com) |
| Docker Compose | v2 | bundled with Docker Desktop |
| Git | any | |

---

## Local Setup

### 1. Clone
```bash
git clone <repo-url>
cd SpendSense
```

### 2. Virtual environment
```bash
python3.13 -m venv venv
source venv/bin/activate          # macOS / Linux
```

### 3. Install dependencies
```bash
pip install --upgrade pip
pip install -r requirements.txt
pip install -r requirements-dev.txt   # pytest extras
```

### 4. Install Playwright Chromium (only needed for `misa.runner`)
```bash
playwright install chromium
# or:
make misa-setup
```

### 5. Configure environment

```bash
# Main env file
cat > .env << 'EOF'
DATABASE_URL=sqlite:///data/txdb.sqlite3
GMAIL_CREDENTIALS_PATH=credentials.json
GMAIL_TOKEN_PATH=token.json
POLL_INTERVAL_SECONDS=300
POLL_ONCE=false
CORRELATION_WINDOW_MINUTES=15
ENV=dev
LOG_LEVEL=INFO
DEBUG=true
TZ=Asia/Singapore
EOF

# MISA credentials (only for misa.runner)
cat > .env.misa << 'EOF'
MISA_USERNAME=your@email.com
MISA_PASSWORD=your_password
EOF
```

### 6. Gmail OAuth2 setup

You need `credentials.json` from Google Cloud Console (Gmail API enabled):

```bash
# Place credentials.json in project root
# Then generate token.json:
python3 -c "from app.gmail.auth import get_gmail_service; get_gmail_service()"
```

A browser will open → sign in with your Google account → `token.json` is created automatically.

> In Docker/CI, set `GMAIL_CREDENTIALS_JSON` and `GMAIL_TOKEN_JSON` as env vars (JSON string values). These override the file paths.

### 7. Initialize the SQLite database

```bash
mkdir -p data
make migrate        # runs: alembic upgrade head
```

---

## Running Workers Locally

### Poller (continuous, every 5 min)
```bash
python -m app.workers.poller_worker
# or:
make poller
```

### Poller (one-shot — poll once then exit)
```bash
POLL_ONCE=true python -m app.workers.poller_worker
# or:
make poller-once
```

### Correlator (optional, every 60s)
```bash
python -m app.workers.correlator_worker
```

### MISA runner (dry run — no browser opened)
```bash
python -m app.misa.runner --start-date 2024-01-01 --end-date 2024-01-31 --dry-run
# or:
make misa MISA_ARGS="--start-date 2024-01-01 --end-date 2024-01-31 --dry-run"
```

### MISA runner (real import, headless)
```bash
python -m app.misa.runner --start-date 2024-01-01 --end-date 2024-01-31
```

### MISA runner (debug — visible browser window)
```bash
python -m app.misa.runner --start-date 2024-01-01 --headed --limit 5
```

---

## Running with Docker

```bash
# Build image
make build

# Start poller
make up

# Detached mode
make upd

# Stop
make down

# Destroy SQLite data volume
make reset-db

# MISA import via Docker Compose
MISA_START_DATE=2024-01-01 MISA_END_DATE=2024-01-31 \
  docker compose --profile misa run --rm misa-runner
```

---

## Running Tests

```bash
# All tests
make test

# Specific test file
pytest tests/test_parser.py -v

# Verbose with print output
pytest tests/ -s -v

# CI-safe (one-shot poller, no live Gmail needed for unit tests)
POLL_ONCE=true pytest tests/test_gmail_polling.py -q
```

### Test files and what they cover

| File | What it tests |
|------|--------------|
| `test_parser.py` | `parse_email()` for all 4 banks — amount, date, sender, receiver, type |
| `test_gmail_polling.py` | `GmailPoller.poll_once()` — idempotency, bank filter, DB insertion |
| `test_classifier.py` | `classifier.classify()` — rule table lookup + fallbacks |
| `test_correlator.py` | `correlate_once()` — amount match, time window, greedy pairing |
| `test_event_builder.py` | `EventBuilder.process_candidate()` |
| `test_misa_client.py` | `client.add_transaction()` — Playwright mock |
| `test_misa_dedup.py` | `DedupStore` — skip already-imported rows |
| `test_misa_query.py` | `misa.query.get_classified_candidates()` — Spend/Earn/skip rules |
| `test_misa_runner.py` | Full `misa.runner` integration test |
| `test_endpoints.py` | Health check endpoint |

---

## Makefile Reference

| Command | What it runs |
|---------|-------------|
| `make poller` | `python -m app.workers.poller_worker` |
| `make poller-once` | `POLL_ONCE=true python -m app.workers.poller_worker` |
| `make misa` | `python -m app.misa.runner --dry-run $(MISA_ARGS)` |
| `make build` | `docker-compose build` |
| `make up` | `docker-compose up` |
| `make upd` | `docker-compose up -d` |
| `make down` | `docker-compose down` |
| `make reset-db` | `docker-compose down -v` |
| `make migrate` | `alembic upgrade head` |
| `make revision` | `alembic revision --autogenerate -m "update"` |
| `make test` | `pytest -q --disable-warnings --maxfail=1` |
| `make lint` | `flake8 app` |
| `make fmt` | `black app tests` |
| `make misa-setup` | `playwright install chromium` |

---

## Database Migrations (Alembic)

```bash
# Apply all migrations
make migrate

# After changing a model in app/db/models/, auto-generate a migration:
make revision
# → creates app/db/migrations/versions/<timestamp>_update.py
# Review the generated file, then:
make migrate
```

The SQLite file lives at `data/txdb.sqlite3`. In Docker, it's bind-mounted from `./data`.

---

## Helper Scripts (`scripts/`)

| Script | Purpose |
|--------|---------|
| `dev_reset.sh` | Drop and recreate local SQLite DB |
| `db_shell.sh` | Open SQLite3 shell on `data/txdb.sqlite3` |
| `new_migration.sh` | Shortcut: generate a new Alembic revision |
| `format.sh` | Run `black` formatter |
| `misa_login_check.py` | Verify MISA credentials open the login page |
| `misa_fill_popup_spend_check.py` | Verify Spend popup automation |
| `misa_fill_popup_earn_check.py` | Verify Earn popup automation |
| `misa_import_click_check.py` | Verify Import button click |
| `test_misa_docker.py` | Full MISA E2E test inside Docker container |
| `tf_backend_bootstrap.sh` | Create S3 bucket for Terraform remote state |

---

## Debugging Tips

### Debug mode
Set `DEBUG=true` in `.env` — the parser and classifier print per-step trace logs:
```
Extracting VND amount...
Applying DBS→PayLah specific date extraction...
Classifying with: inferred_sender=DBS, inferred_receiver=PayLah, ...
Mapping raw name 'ending 7013' to canonical account 'DBS' using variant 'ending 7013'
```

### Inspect the SQLite database directly
```bash
bash scripts/db_shell.sh
# Inside sqlite3:
.tables
SELECT id, from_email, subject FROM email_raw ORDER BY received_at DESC LIMIT 5;
SELECT inferred_sender, inferred_receiver, amount, type_info FROM parsed_transaction_candidate LIMIT 10;
SELECT * FROM misa_import_state ORDER BY imported_at DESC LIMIT 5;
```

### Test the parser on a real email body
```python
from app.parsing.parser import parse_email, extract_plain_text
html = open("path/to/email.html").read()
plain = extract_plain_text(html)
result = parse_email("Subject here", plain)
print(result)
```

### Check MISA login manually
```bash
python scripts/misa_login_check.py
```

### Run MISA dry-run to see what would be imported
```bash
python -m app.misa.runner --start-date 2024-01-01 --dry-run
```
