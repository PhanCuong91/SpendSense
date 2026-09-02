# Requirements: Export Spend/Earn Transactions to MISA Money Keeper

## 1. Overview
Build a Python script that reads confirmed Spend/Earn transactions from the local
`data/txdb.sqlite3` database and imports them into MISA Money Keeper
(https://moneykeeperapp.misa.vn/management/transactions) by driving the web UI
with a browser automation library, since MISA does not expose a public API for
this workspace. The script logs a per-row success/failure result and a final
summary.

## 2. Data Source

### 2.1 Table and filter
- Source table: `parsed_transaction_candidate` (`app/db/models/parsed_candidate.py`).
- Classification is based **only** on `inferred_sender` / `inferred_receiver`
  (`debit_credit` and `type_info` are not used):
  - **Spend**: `inferred_sender != "Other"` AND `inferred_receiver == "Other"`.
  - **Earn**: `inferred_sender == "Other"` AND `inferred_receiver != "Other"`.
- Confirmed against real data (202 rows in `txdb.sqlite3` at time of writing):
  182 rows match the Spend pattern and 5 rows match the Earn pattern.

### 2.2 Field mapping
| MISA field | Source | Rule |
|---|---|---|
| Amount     | `parsed_transaction_candidate.amount` | direct copy |
| Account    | `inferred_sender` or `inferred_receiver` | `inferred_sender` when the row resolves to **Spend** (`inferred_sender != "Other"` and `inferred_receiver == "Other"`); `inferred_receiver` when it resolves to **Earn** (`inferred_sender == "Other"` and `inferred_receiver != "Other"`) |
| Date/time  | `datetime_sgt` | direct copy, converted to `DD/MM/YYYY HH:MM` (confirmed MISA date field format, see §10.2) |
| Category   | fixed default, **per classification** | `"Bars & Coffee"` for Spend rows; `"Balance"` for Earn rows (confirmed 2026-08-07: Spend and Earn have distinct/non-overlapping category lists in MISA, so a single fixed category cannot serve both — see `app/misa/mapper.py` `CATEGORY`/`EARN_CATEGORY`) |

## 3. MISA Web Automation

### 3.1 Library
- Use **Playwright for Python** (`playwright`).
- Playwright is **not** part of the production runtime dependencies in `requirements.txt`.
  It is installed separately on the EC2 instance that runs the MISA import, because:
  - Playwright + Chromium binaries add ~1-2 GB to the Docker image.
  - The MISA runner does not run in the ECS Fargate task (headless Chromium cannot handle interactive login/2FA).
  - Keeping the image small reduces ECR storage cost and speeds up ECS task startup.
- The deployment EC2 user-data script installs Playwright at runtime before invoking the MISA runner.
- For local development and tests, install Playwright manually: `pip install playwright && playwright install chromium`.

### 3.2 Login
- Credentials supplied via environment variables (`MISA_USERNAME`, `MISA_PASSWORD`),
  loaded from a local `.env` file (already using `python-dotenv` in this project) —
  **never committed to git**.
- If MISA requires 2FA/captcha that cannot be automated, the script should support
  a `--headed` / interactive fallback mode where the browser is opened visibly and
  the user can complete login manually before the script continues.
- On the deployment EC2 instance the runner logs in fresh each day. Persisting
  `storage_state` between runs is optional and not required for cost savings.

### 3.3 Selectors / DOM structure
- **Mostly confirmed (2026-08-08).** All selectors for the login form, the
  "Import" button, the popup Spend/Earn tabs, and all Spend/Earn field inputs
  are isolated in `app/misa/selectors.py` and confirmed working via manual
  scripts.
- Remaining uncertainty: `LOGIN_2FA_INDICATOR`, `SUCCESS_INDICATOR`, and
  `ERROR_INDICATOR` are still guessed/never matched in practice (the real
  success signal appears to be the popup closing, not a toast).
- All selectors must remain isolated in `app/misa/selectors.py` so live-site
  changes can be updated without touching core logic.

### 3.4 Per-transaction flow
For each row to import:
1. Click the "Import"/"Add transaction" button.
2. Wait for the popup form to appear (an async default-account load also
   starts here and must be allowed to settle, see §10.4).
3. Click the Spend or Earn tab per the row's classification (switching tabs
   re-triggers the same async default-account load — must settle again,
   see §10.4).
4. Fill Amount, Date fields; select Account and Category from their
   respective dropdowns (typing text alone only filters the dropdown — the
   matching option must be explicitly clicked to commit the selection, see
   §10.5).
5. Click the Save-and-close button ("Lưu", confirmed 2026-08-08).
6. Verify the popup closed / a success indicator appeared (or detect an error
   message/validation failure).
7. Record success or failure for that row.

The implementation lives in `app/misa/client.py::add_transaction()`, which
now handles Spend/Earn tab switching, the post-tab-switch settle wait,
category option click, and Save-and-close.

### 3.5 Error Recovery — Reload / Re-login on Import Failure

When an error occurs during an individual transaction import (e.g. the popup
gets into a broken state, a network blip causes the page to go blank, or the
browser context becomes stale), the runner must attempt to recover before
moving on to the next row rather than failing the remainder of the run silently.

**Recovery sequence (applied per-row on any exception or detected error):**

1. **Detect the failure** — catch any Playwright exception (`TimeoutError`,
   `Error`) or a detected `ERROR_INDICATOR` on the page after the Save
   attempt.
2. **Attempt page reload first** — call `page.reload()` and wait for the
   transactions page to be ready (network idle / `TRANSACTIONS_URL` loaded).
   - If the reload lands on the login page (session expired), proceed to
     step 3.
   - If the reload lands on the transactions page successfully, resume
     importing the next row from that page — **do not retry the failed row**
     (it has not been marked as imported, so it will be picked up on the
     next runner invocation).
3. **Re-login if the session is gone** — if after the reload the page is on
   the login URL or the `LOGIN_SUCCESS_INDICATOR` is absent, call
   `client.login(page, username, password)` and, on success,
   `client.save_session(context)` to refresh the stored session state.
   - If re-login succeeds, resume importing the next row.
   - If re-login fails, **abort the run** immediately (log a fatal error and
     return exit code 1) — continuing without a valid session would silently
     skip all remaining rows.
4. **Log the recovery action** — always emit a log line indicating which row
   failed, what recovery was attempted (reload vs re-login), and whether it
   succeeded, so post-run analysis can identify flaky sessions or persistent
   MISA UI bugs.

**Scope:** this recovery applies only between rows, not within the steps of
a single row's import flow (§3.4). A row whose import raises an error is
logged as failed and is eligible for retry on the next run via the dedup
store (§4).

## 4. Duplicate Import Prevention
- Maintain the import state in the **SQLite database** itself, in a dedicated table
  `misa_import_state` (see §4.1), instead of a local JSON file.
- On each run, skip rows already recorded as `status = "imported"` in that table.
- Only mark a row as imported **after** a confirmed successful save in MISA (see §5).
  Rows that fail must remain eligible for retry on the next run.
- Because the SQLite DB is backed up to and restored from S3, the import state
  automatically survives across ECS runs and EC2 MISA import runs without any
  separate file sync.

### 4.1 State table schema

Implemented in [app/db/models/misa_import_state.py](app/db/models/misa_import_state.py):

```python
class MisaImportState(Base):
    __tablename__ = "misa_import_state"

    parsed_candidate_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("parsed_transaction_candidate.id", ondelete="CASCADE"),
        primary_key=True,
    )
    imported_at = Column(TIMESTAMP(timezone=True), nullable=False)
    amount = Column(Numeric(18, 2), nullable=True)
    account = Column(String, nullable=True)
    datetime = Column(String, nullable=True)
    classification = Column(String, nullable=True)
    status = Column(String, nullable=False, default="imported")
```

The dedup store ([app/misa/dedup_store.py](app/misa/dedup_store.py)) also
auto-creates the table if it is missing, so the runner works against older
DB files that pre-date the Alembic migration.

- `parsed_candidate_id`: references the imported candidate.
- `imported_at`: UTC timestamp of the import.
- `amount`, `account`, `datetime`, `classification`: snapshot of the MISA transaction
  for audit/debugging.
- `status`: `"imported"` on success. Failed attempts are **not** written, so the row
  remains eligible for retry.

## 5. Logging
- For each row attempted, print a log line indicating success or failure, including
  at minimum: candidate id, amount, account, datetime, and (on failure) the reason/
  error encountered.
- At the end of the run, print a summary: total candidates considered, number
  imported successfully, number failed, number skipped (already imported).
- Use the project's existing logging setup (`app/core/logging.py`) if suitable, or
  a standalone `logging` configuration for this script if it is meant to run
  independently of the FastAPI app.

## 6. Scope / Date Range
- Default: import all eligible Spend/Earn rows not already recorded in the import
  state table (see §4) — i.e., dedup by id is the primary filter.
- In the AWS deployment, the EC2 MISA runner is invoked with `--start-date` and
  `--end-date` set to **yesterday and today** (inclusive), to cover the transactions
  just ingested by the daily ECS run.
- Optionally support `--start-date` / `--end-date` CLI arguments for ad-hoc/backfill
  runs.
- `--state-file` is no longer supported; dedup state is always read from and
  written to the `misa_import_state` table.

## 7. Non-Functional Requirements
- **Security**: MISA credentials must never be hardcoded or committed; load from
  `.env.misa`/environment only. `.env.misa` must be in `.gitignore` (verify).
- **Reliability**: the script must be safe to re-run (idempotent) thanks to the
  dedup state table; a mid-run crash must not double-import rows already confirmed
  as saved.
- **Resilience**: individual row failures (e.g. a validation error in the MISA form)
  must not stop the whole run — log and continue to the next row. On any error,
  the runner must attempt to recover the browser session via a page reload or
  re-login before continuing (see §3.5). The run is aborted only when re-login
  itself fails, to prevent silently skipping rows without a valid session.

## 8. Acceptance Criteria
1. Running the script imports all not-yet-imported Spend/Earn rows from
   `txdb.sqlite3` into MISA via the web UI.
2. Each imported transaction in MISA shows the correct amount, account, date, and
   the fixed category `"Bars & Coffee"`.
3. Re-running the script does not re-import previously successful rows.
4. Console/log output clearly shows per-row success/failure and an end-of-run
   summary.
5. No MISA credentials are stored in the repository.
6. When a row import fails, the runner performs a page reload (or re-login if
   the session has expired) before continuing to the next row. The failed row
   is logged clearly and remains eligible for retry on the next run. If
   re-login itself fails, the run aborts with a non-zero exit code and a fatal
   log message.

## 9. Testing Requirements
Tests should follow the existing convention in `tests/` (pytest, e.g.
`tests/test_event_builder.py`) and live in a new `tests/test_misa_import.py`.

### 9.1 Unit tests (no browser, no network)
1. **Row selection/classification** — given a set of `parsed_transaction_candidate`
   rows, verify the Spend/Earn filter from §2.1 selects/excludes the right rows,
   including edge cases confirmed against real data:
   - `inferred_sender != "Other"` and `inferred_receiver == "Other"` → classified Spend.
   - `inferred_sender == "Other"` and `inferred_receiver != "Other"` → classified Earn.
   - both `"Other"` (e.g. NULL/unparsed rows) → excluded.
   - neither `"Other"` (InternalTransfer legs, e.g. `DBS`→`Trust`) → excluded.
2. **Field mapping** — verify Amount/Account/Date/Category are mapped per §2.2 for
   both a Spend row and an Earn row (Account = `inferred_sender` vs `inferred_receiver`
   respectively), and that `Category` is always the fixed default.
3. **Dedup/state table** — verify a row already recorded as imported in the
   `misa_import_state` table (§4) is skipped on a subsequent run, and a failed row
   is *not* recorded and remains eligible for retry.
4. **Date/time formatting** — verify `datetime_sgt` is converted to the exact
   string format MISA's form expects (once confirmed, see §10.2).

### 9.2 Browser-automation tests (mocked MISA UI)
1. Use Playwright against a local static HTML fixture that mimics the MISA login
   page, Import button, and popup form (rather than the real site), so tests run
   without network access or real credentials.
2. Verify the login flow submits the right fields and detects success/failure.
3. Verify the per-transaction flow (§3.4: click Import → fill popup → Save) fills
   the correct field values and correctly detects both a success indicator and a
   validation/error indicator, feeding into per-row logging (§5).
4. Verify a mid-run failure on one row does not stop processing of subsequent rows.

### 9.3 Manual/exploratory testing (against the real MISA site)
1. A dry run against a MISA sandbox/test account (not production data) to validate
   selectors once available (§3.3/§10.1), before running against real data.
2. Manually verify imported transactions in the MISA UI match amount, account,
   date, and category for at least one Spend and one Earn row.
3. Verify re-running the script against already-imported data produces no
   duplicates in MISA.

## 10. Open Items Requiring Follow-Up
1. ~~Obtain real selectors/HTML for the MISA login page, Import button, and
   popup form (see §3.3).~~ **Mostly resolved (2026-08-07)** — login,
   Import button, both tabs, and all Spend/Earn field selectors are
   confirmed working end-to-end via manual scripts. Remaining gap: the
   real "Lưu" (Save & Close) button selector is still unknown (see §10.6).
2. ~~Confirm date/time format expected by the MISA date field.~~ **Resolved
   (2026-08-07)**: `DD/MM/YYYY HH:MM`.
3. Confirm whether 2FA/captcha is present on MISA login (affects headless vs
   interactive login flow). **Still open** — 2FA has never actually been
   triggered during testing so far; the indicator selector remains a
   guess.
4. **Resolved (2026-08-08)** — the dedup state migration is done and the
   `misa_import_state` table is created automatically if missing.
5. **Resolved (2026-08-08)** — `requirements.txt` no longer contains
   Playwright; local dev uses `requirements-dev.txt`.
6. **Resolved (2026-08-08)** — `client.py::add_transaction()` now switches
   tabs, clicks category options, waits for the async account load, and uses
   the Save-and-close button.
4. **(New, 2026-08-07)** Async default-account bug: MISA's popup
   asynchronously loads/overwrites a default account ~1-2.5s after the
   popup opens AND again after switching tabs. Any account selection made
   before this settles is silently reverted. Mitigation (a fixed
   `wait_for_timeout`) is implemented for the popup-open case in
   `client.py`; the tab-switch case is only handled in the manual Earn
   test script so far, not in `client.py`/`add_transaction()`.
5. **(New, 2026-08-07)** Category dropdown selection requires an explicit
   click on the matching option after typing — `fill()` alone only filters
   the list and does not commit the selection, so Save is blocked by
   validation if only `fill()` is used. Currently only implemented in the
   manual Earn test script, not yet in `client.py`.
6. ~~MISA's popup has two Save buttons — "Lưu" (Save & Close) and "Lưu và
   thêm" (Save & Add Another).~~ **Resolved (2026-08-08)** — both are now
   confirmed: `POPUP_SAVE_AND_ADD_BUTTON` ("Lưu và thêm") and
   `POPUP_SAVE_AND_CLOSE_BUTTON` ("Lưu", exact-text match scoped to the
   footer). Verified live via `scripts/misa_fill_popup_spend_check.py`:
   clicking `POPUP_SAVE_AND_CLOSE_BUTTON` closes the popup and the new row
   appears in the transaction list, unlike `POPUP_SAVE_AND_ADD_BUTTON`
   which leaves it open. `client.py`'s `add_transaction()` still needs to
   be switched over to use `POPUP_SAVE_AND_CLOSE_BUTTON` (currently uses
   the Add-Another one).
7. **(New, 2026-08-08)** Migrate dedup state from JSON file to
   `misa_import_state` DB table (§4). This affects `app/misa/runner.py`,
   `app/misa/dedup_store.py`, and the test suite.
8. **(New, 2026-08-08)** Remove Playwright from `requirements.txt` and
   document the separate EC2 runtime installation (§3.1).
