# Configuration Reference — SpendSense

All configuration is loaded from environment variables via `pydantic-settings` (see `app/core/config.py`).

There are **two env files**:
- `.env` — main app config (committed to `.gitignore`)
- `.env.misa` — MISA credentials only (extra-sensitive, gitignored separately)

---

## Core Settings

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DATABASE_URL` | ✅ | — | SQLite connection string. Example: `sqlite:////app/data/txdb.sqlite3` |
| `ENV` | ❌ | `dev` | Environment name (`dev`, `prod`) |
| `TZ` | ❌ | `Asia/Singapore` | Container timezone (set in docker-compose) |
| `LOG_LEVEL` | ❌ | `INFO` | Logging level: `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `DEBUG` | ❌ | `true` | Enable debug mode |

---

## Gmail API Settings

Gmail OAuth2 credentials can be provided as **file paths** (local dev) or **JSON strings** (Docker / CI).

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `GMAIL_CREDENTIALS_PATH` | ❌ | `credentials.json` | Path to OAuth2 credentials file |
| `GMAIL_TOKEN_PATH` | ❌ | `token.json` | Path to OAuth2 token file |
| `GMAIL_CREDENTIALS_JSON` | ❌* | — | Full credentials JSON as a string (overrides path) |
| `GMAIL_TOKEN_JSON` | ❌* | — | Full token JSON as a string (overrides path) |

> *In CI/CD and Docker, provide `GMAIL_CREDENTIALS_JSON` and `GMAIL_TOKEN_JSON` as GitHub Secrets / AWS SSM Parameter Store values. These override the file path settings.

### Getting Gmail credentials
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Enable the Gmail API
3. Create OAuth2 credentials → Download as `credentials.json`
4. Run the OAuth2 flow once locally to generate `token.json`

---

## Pipeline Settings

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `POLL_INTERVAL_SECONDS` | ❌ | `300` | How often `poller_worker` polls Gmail (seconds) |
| `POLL_ONCE` | ❌ | `false` | If `true`, poller runs once then exits (for CI tests) |
| `CORRELATION_WINDOW_MINUTES` | ❌ | `15` | Max time difference for matching debit/credit pairs |

---

## MISA Settings (`.env.misa`)

Stored in `.env.misa` — **never commit this file**.

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `MISA_USERNAME` | ✅ | — | MISA Money Keeper login email |
| `MISA_PASSWORD` | ✅ | — | MISA Money Keeper login password |

### Docker Compose MISA args
When running `misa-runner` via Docker Compose:

| Variable | Description |
|----------|-------------|
| `MISA_START_DATE` | Start date filter `YYYY-MM-DD` (passed as `--start-date`) |
| `MISA_END_DATE` | End date filter `YYYY-MM-DD` (passed as `--end-date`) |
| `MISA_RUNNER_EXTRA_ARGS` | Additional CLI args (e.g. `--dry-run`, `--headed`, `--limit 10`) |

---

## Docker Build Args

| Arg | Default | Description |
|-----|---------|-------------|
| `APP_VERSION` | `dev` | Image version tag (set by CI from git SHA) |
| `VCS_REF` | `local` | Git commit SHA (added as OCI label) |
| `BUILD_DATE` | `unknown` | Build timestamp (added as OCI label) |

---

## Runtime Role Selection

The `APP_ROLE` env var switches which worker the container runs:

| `APP_ROLE` | Command executed |
|-----------|-----------------|
| `poller` | `python -m app.workers.poller_worker` |
| `correlator` | `python -m app.workers.correlator_worker` |
| `misa` | `python -m app.misa.runner [--start-date] [--end-date] [extra args]` |

---

## Example `.env`

```bash
# Database
DATABASE_URL=sqlite:////app/data/txdb.sqlite3

# Gmail (file paths — local dev)
GMAIL_CREDENTIALS_PATH=credentials.json
GMAIL_TOKEN_PATH=token.json

# Gmail (JSON strings — Docker / CI, overrides paths)
# GMAIL_CREDENTIALS_JSON={"installed":{"client_id":"...","client_secret":"...",...}}
# GMAIL_TOKEN_JSON={"token":"...","refresh_token":"...",...}

# Pipeline
POLL_INTERVAL_SECONDS=300
POLL_ONCE=false
CORRELATION_WINDOW_MINUTES=15

# App
ENV=dev
LOG_LEVEL=INFO
DEBUG=true
TZ=Asia/Singapore
```

## Example `.env.misa`

```bash
MISA_USERNAME=your_misa_email@example.com
MISA_PASSWORD=your_misa_password
```
