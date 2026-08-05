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
| Date/time  | `datetime_sgt` | direct copy, converted to whatever date/time format the MISA form expects |
| Category   | fixed default | `"Bar & Coffee"` for every imported row (no per-row derivation) |

## 3. MISA Web Automation

### 3.1 Library
- Use **Playwright for Python** (`playwright`). Not currently in `requirements.txt` —
  must be added, plus running `playwright install` for the chromium browser.

### 3.2 Login
- Credentials supplied via environment variables (`MISA_USERNAME`, `MISA_PASSWORD`),
  loaded from a local `.env` file (already using `python-dotenv` in this project) —
  **never committed to git**.
- If MISA requires 2FA/captcha that cannot be automated, the script should support
  a `--headed` / interactive fallback mode where the browser is opened visibly and
  the user can complete login manually before the script continues.
- Reuse Playwright's `storage_state` (cookies/local storage) to persist a logged-in
  session between runs where possible, to avoid logging in every time.

### 3.3 Selectors / DOM structure
- **Not yet available.** The exact selectors for the login form, the "Import" button
  on the transactions page, and the popup/modal form fields (amount, account, date,
  category, save button) are unknown at spec time.
- The implementation must isolate all selectors in one place (e.g. a `selectors.py`
  config module or constants block) so they can be updated after inspecting the live
  page (via browser DevTools) without touching the core logic.
- Before writing the final selectors, a short manual inspection pass of the real
  MISA "Add Transaction" popup is required (recorded separately, not part of this
  requirements doc).

### 3.4 Per-transaction flow
For each row to import:
1. Click the "Import"/"Add transaction" button.
2. Wait for the popup form to appear.
3. Fill Amount, Account, Date, Category fields.
4. Click Save.
5. Verify the popup closed / a success indicator appeared (or detect an error
   message/validation failure).
6. Record success or failure for that row.

## 4. Duplicate Import Prevention
- Maintain a local state file (e.g. JSON, keyed by `parsed_transaction_candidate.id`)
  recording which candidate rows have already been successfully imported to MISA.
- On each run, skip rows already present in the state file.
- Only mark a row as imported in the state file **after** a confirmed successful save
  in MISA (see §5). Rows that fail must remain eligible for retry on the next run.
- Location suggestion: `ai/update_misa_implementation/imported_state.json` or a path
  configurable via CLI/env var.

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
- Default: import all eligible Spend/Earn rows not already recorded in the local
  state file (see §4) — i.e., dedup by id is the primary filter.
- Optionally support `--start-date` / `--end-date` CLI arguments to further restrict
  by `datetime_sgt`, for ad-hoc/backfill runs. Exact default range still to be
  confirmed with the user if simple "not yet imported" is not sufficient.

## 7. Non-Functional Requirements
- **Security**: MISA credentials must never be hardcoded or committed; load from
  `.env`/environment only. `.env` must be in `.gitignore` (verify).
- **Reliability**: the script must be safe to re-run (idempotent) thanks to the
  dedup state file; a mid-run crash must not corrupt the state file or double-import
  rows already confirmed as saved.
- **Resilience**: individual row failures (e.g. a validation error in the MISA form)
  must not stop the whole run — log and continue to the next row.

## 8. Acceptance Criteria
1. Running the script imports all not-yet-imported Spend/Earn rows from
   `txdb.sqlite3` into MISA via the web UI.
2. Each imported transaction in MISA shows the correct amount, account, date, and
   the fixed category `"Bar & Coffee"`.
3. Re-running the script does not re-import previously successful rows.
4. Console/log output clearly shows per-row success/failure and an end-of-run
   summary.
5. No MISA credentials are stored in the repository.

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
3. **Dedup/state file** — verify a row already recorded as imported in the state
   file (§4) is skipped on a subsequent run, and a failed row is *not* recorded and
   remains eligible for retry.
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
1. Obtain real selectors/HTML for the MISA login page, Import button, and popup
   form (see §3.3) — required before the automation logic can be finalized.
2. Confirm date/time format expected by the MISA date field.
3. Confirm whether 2FA/captcha is present on MISA login (affects headless vs
   interactive login flow).
