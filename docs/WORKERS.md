# Workers Reference — SpendSense

SpendSense uses a **single Docker image** switched by `APP_ROLE`. All workers share the same SQLite file at `data/txdb.sqlite3`.

---

## Worker Summary

| Worker | `APP_ROLE` | Mode | Default interval |
|--------|-----------|------|-----------------|
| `poller_worker` | `poller` | Infinite loop | Every 300s (5 min) |
| `parser_worker` | _(inline)_ | Synchronous call | Per email ingested |
| `correlator_worker` | `correlator` | Infinite loop | Every 60s |
| `misa.runner` | `misa` | One-shot CLI | On demand |

---

## 1. `poller_worker` — Gmail Poller

**Source:** [`app/workers/poller_worker.py`](../app/workers/poller_worker.py)  
**Logic:** [`app/gmail/poller.py`](../app/gmail/poller.py)

### Execution flow

```
while True:
    GmailPoller.poll_once()
    sleep(POLL_INTERVAL_SECONDS)   # default 300
```

### `poll_once()` detail

```
1. Ensure email_raw table exists (auto-creates if missing)
2. gmail_client.list_messages("newer_than:1d", page_token)
3. for each message:
   a. Check email_raw.gmail_message_id == msg_id  → SKIP if exists (idempotent)
   b. gmail_client.get_message(msg_id)
   c. Extract from_email from headers
   d. from_bank_email(from_email)?  → SKIP if not in known list
      Allowed senders:
        mailalert@acb.com.vn
        ibanking.alert@dbs.com
        paylah.alert@dbs.com
        from_us@trustbank.sg
   e. decode_email(payload, msg_id)  → (subject, body)
   f. INSERT INTO email_raw
   g. parser_worker.enqueue_for_parsing(email_raw.id)
4. Follow nextPageToken until exhausted
```

### Configuration

| Env Var | Default | Description |
|---------|---------|-------------|
| `POLL_INTERVAL_SECONDS` | `300` | Sleep between poll cycles |
| `POLL_ONCE` | `false` | `true` → run once then exit (CI mode) |
| `DATABASE_URL` | required | `sqlite:////app/data/txdb.sqlite3` |
| `GMAIL_CREDENTIALS_JSON` | required* | OAuth2 credentials JSON string |
| `GMAIL_TOKEN_JSON` | required* | OAuth2 token JSON string |
| `GMAIL_CREDENTIALS_PATH` | `credentials.json` | File path (local dev, overridden by JSON var) |
| `GMAIL_TOKEN_PATH` | `token.json` | File path (local dev, overridden by JSON var) |

### One-shot mode (for CI)
```bash
POLL_ONCE=true python -m app.workers.poller_worker
```
Used in GitHub Actions so tests don't run an infinite loop.

### Run
```bash
# locally
python -m app.workers.poller_worker

# Docker
docker compose up poller-worker

# Makefile
make poller         # continuous
make poller-once    # one-shot
```

---

## 2. `parser_worker` — Email Parser + Classifier

**Source:** [`app/workers/parser_worker.py`](../app/workers/parser_worker.py)  
**Core parsing:** [`app/parsing/parser.py`](../app/parsing/parser.py)

> **Not standalone.** Called synchronously by `poller_worker` via `enqueue_for_parsing(email_raw.id)`.  
> Comment in code: `"Direct synchronous parsing for now. Replace with RQ/Celery later."`

### Execution flow per email

```
parse_email_task(email_id):
  1. Ensure parsed_transaction_candidate table exists
  2. Fetch EmailRaw by id
  3. extract_plain_text(html_body)  → BeautifulSoup strip tags
  4. parse_email(subject, plain_text):
       a. normalize_whitespace(subject + " " + body)
       b. extract_amount(text):
            if "SGD" in text:
              AMOUNT_REGEX_SGD → named groups: currency, amount
            elif "VND" in text:
              AMOUNT_REGEX_VND (findall) → take LAST match if multiple
       c. extract_parties(body):
            try DBS/PayLah: FROM_LINE / TO_LINE regex
            try TrustBank:  TRUST_SPENT / TRUST_RECEIVED regex
            try ACB:        keyword "debit"/"credit" + account number heuristics
       d. map_account_alias(raw_sender/receiver):
            "ending 7013"   → DBS
            "ending 3162"   → PayLah
            "Trust*"        → Trust
            "WESTERN UNION" → ACB Online
            "ACB Online"    → ACB Online
            "ACB"           → ACB
            fallback        → "Other"
       e. detect_debit_credit(sender, receiver, text)
       f. dectect_type(sender, receiver, text)  → Spend/Earn/InternalTransfer
       g. extract_date(sender, receiver, text):
            DBS→PayLah: DATE_PATTERNS_DBS_2_PAYLAH
            others:     DATE_PATTERNS (4 patterns, first match wins)
  5. INSERT INTO parsed_transaction_candidate
```

### Bank-specific parsing rules

#### DBS / PayLah emails
| Field | Method |
|-------|--------|
| Sender | `FROM_LINE = re.compile(r"From:\s*(.*?)\s*To:", re.DOTALL)` |
| Receiver | `TO_LINE = re.compile(r"To:\s*(.*)", re.IGNORECASE)` |
| Date | Special `DATE_PATTERNS_DBS_2_PAYLAH` if sender=DBS + receiver=PayLah |
| Amount | `AMOUNT_REGEX_SGD` → `SGD(\$)?\s?<amount>` |
| InternalTransfer signals | `"(NRIC ending 014U)"`, `"WESTERN UNION"`, `"You've successfully top-up to your PayLah!"` |

#### TrustBank emails
| Field | Method |
|-------|--------|
| Sender | `TRUST_SPENT = re.compile(r"You've spent\s*(.*)")` |
| Receiver | `TRUST_RECEIVED = re.compile(r"You've received\s*(.*)")` |
| Fallback sender | `"You've received a PayNow transfer"` → DBS |
| Fallback receiver | `"(ending 014)"` → Trust |
| InternalTransfer | receiver=Trust + `"You've received a PayNow transfer"` |

#### ACB (Vietnam) emails
| Field | Method |
|-------|--------|
| Direction | `"debit"` in body → spend; `"credit"` → earn |
| Account | `"6422417"` → ACB Online; else → ACB |
| Amount | `AMOUNT_REGEX_VND` → `[+-]?<digits> VND` (last match wins) |
| InternalTransfer signals | `"FINFAN"` in text, `"Debit -"` for ACB Online |

### Date regex patterns

```python
DATE_PATTERNS = [
    r"dated (?P<day>\d{1,2})\s(?P<mon>\w{3})",           # "dated 02 Mar"
    r"(?P<day>\d{1,2})\s(?P<mon>\d{1,2}|[A-Z][a-z]*)\s(?P<yyyy>\d{2,4}) ",  # "02 Mar 2026"
    r"(?P<dd>\d{2})\/(?P<mm>\d{2})\/(?P<yy>\d{2,4})",    # "03/03/2026" ACB format
    r"(?P<dd>\d{2})(?P<mm>\d{2})(?P<yy>\d{2})-",         # "030326-11:54:07"
]
DATE_PATTERNS_DBS_2_PAYLAH = [
    r"(?P<day>\d{2}) (?P<mon>\w{3})\d{2}:",               # "02 Mar23:" DBS→PayLah
]
```

---

## 3. `correlator_worker` — Debit/Credit Correlator

**Source:** [`app/workers/correlator_worker.py`](../app/workers/correlator_worker.py)  
**Logic:** [`app/correlation/correlator.py`](../app/correlation/correlator.py)

> **Optional worker.** Present in `docker-compose.yaml` but not part of the primary pipeline. Enables matching 2-email InternalTransfer events (e.g. DBS→Trust where both banks send an alert).

### Execution flow

```
while True:
    correlate_once()
    sleep(60)
```

### `correlate_once()` detail

```
1. PendingStore.get_pending(session, DebitCredit.debit)   → list of unmatched debits
2. PendingStore.get_pending(session, DebitCredit.credit)  → list of unmatched credits

3. If no credits and debits exist:
     handle_unmatched_debits():
       for each debit, if NO existing Event contains its email_id
       AND debit is older than 120 minutes:
         → CREATE Event(type=InternalTransfer) from single debit

4. Score all debit×credit pairs:
     _candidate_match_score(debit, credit):
       if debit.amount != credit.amount  → -1  (skip)
       if |Δt| > CORRELATION_WINDOW_MINUTES (default 15)  → -1
       score = (15 - |Δt|) / 10         (0.0 – 1.5 range)

5. Greedy best-match (sort by score DESC, skip already-used):
     for each (debit, credit) final pair:
       → INSERT Event(type=InternalTransfer, sender=debit.sender, receiver=credit.receiver)
       → INSERT CorrelationLink(debit_id, credit_id, event_id)
```

### Configuration

| Env Var | Default | Description |
|---------|---------|-------------|
| `CORRELATION_WINDOW_MINUTES` | `15` | Max timestamp gap (minutes) to consider a match |

### Run
```bash
# Docker
docker compose up correlator-worker

# locally
python -m app.workers.correlator_worker
```

---

## 4. `misa.runner` — MISA Batch Importer

**Source:** [`app/misa/runner.py`](../app/misa/runner.py)  
**Browser client:** [`app/misa/client.py`](../app/misa/client.py)  
**Query/classify:** [`app/misa/query.py`](../app/misa/query.py)

### Execution flow

```
1. Load .env.misa → MISA_USERNAME, MISA_PASSWORD
2. Open DB session
3. misa.query.get_classified_candidates(db, start_date, end_date):
     for each parsed_transaction_candidate:
       Spend  → sender != "Other" AND receiver == "Other"
       Earn   → sender == "Other" AND receiver != "Other"
       Skip   → both "Other" (unparsed) or both known (InternalTransfer leg)

4. DedupStore: filter out rows already in misa_import_state

5. if --dry-run:
     print table of planned imports → exit

6. Launch Playwright Chromium (headless unless --headed)
7. client.is_logged_in(page):
     → try storage_state cache first (misa.storage_state.json)
     → fallback: login with username/password

8. for each (candidate, classification):
     client.add_transaction(page, MisaTransaction(
       amount, account, datetime, classification
     ))
     ├─ Click Import button
     ├─ Wait for popup (POPUP_TIMEOUT_MS=10s)
     ├─ Set account field (wait POPUP_ACCOUNT_SETTLE_MS=2.5s for default to settle)
     ├─ Fill amount (Vietnamese format: "," as decimal separator)
     ├─ Fill date/time
     ├─ Click Save & Close
     ├─ Wait for save outcome
     └─ _wait_for_save_outcome() polls every 250ms up to POPUP_TIMEOUT_MS
     on success:
       INSERT INTO misa_import_state
     on failure:
       log error, continue to next row

9. Print summary: N imported, M failed
```

### MISA amount formatting

MISA Web uses **Vietnamese number format** (comma as decimal separator):

```python
def format_misa_amount(amount) -> str:
    # 123.45 → "123,45"
    # 100.00 → "100"   (no trailing zeros)
```

### CLI flags

```
python -m app.misa.runner [OPTIONS]

  --start-date YYYY-MM-DD   Filter candidates from this date (inclusive)
  --end-date   YYYY-MM-DD   Filter candidates up to this date (inclusive)
  --dry-run                 Print import plan, skip browser launch
  --headed                  Run Chromium in visible window (debug mode)
  --limit N                 Import at most N rows per run
```

### Playwright timeouts

| Constant | Value | Purpose |
|----------|-------|---------|
| `LOGIN_TIMEOUT_MS` | 15,000ms | Wait for session restore check |
| `INTERACTIVE_LOGIN_TIMEOUT_MS` | 120,000ms | Wait for manual login (2 min) |
| `POPUP_TIMEOUT_MS` | 10,000ms | Wait for import popup to open |
| `POPUP_ACCOUNT_SETTLE_MS` | 2,500ms | Wait for default account to settle before input |
| `POPUP_CLOSE_SETTLE_MS` | 2,000ms | Wait for popup to fully close after save |

### Credentials

`.env.misa`:
```bash
MISA_USERNAME=your@email.com
MISA_PASSWORD=your_password
```

Session state is cached at `ai/update_misa_implementation/misa.storage_state.json` and reused on subsequent runs to avoid re-login.

### Run
```bash
# Dry run — no browser
python -m app.misa.runner --start-date 2024-01-01 --end-date 2024-01-31 --dry-run

# Real import
python -m app.misa.runner --start-date 2024-01-01 --end-date 2024-01-31

# Debug — watch the browser
python -m app.misa.runner --start-date 2024-01-01 --headed --limit 5

# Via Docker Compose (with profile)
MISA_START_DATE=2024-01-01 MISA_END_DATE=2024-01-31 \
  docker compose --profile misa run --rm misa-runner

# Makefile
make misa MISA_ARGS="--start-date 2024-01-01 --end-date 2024-01-31"
```

> `misa-runner` uses `restart: "no"` in docker-compose — it exits after one run.

---

## Worker Startup Order

```bash
# 1. Start poller (primary — always running)
docker compose up -d poller-worker

# 2. Start correlator (optional — for inter-bank transfer matching)
docker compose up -d correlator-worker

# 3. Run MISA import on demand
MISA_START_DATE=2024-01-01 MISA_END_DATE=2024-01-31 \
  docker compose --profile misa run --rm misa-runner
```
