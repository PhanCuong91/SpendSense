# Task: Export Spend/Earn Transactions to MISA Money Keeper

## 1. Objective
Implement the `app/misa/` module and its tests so that running
`python -m app.misa.runner` imports all not-yet-imported Spend/Earn rows from
`data/txdb.sqlite3` into MISA Money Keeper
(https://moneykeeperapp.misa.vn/management/transactions), with duplicate-import
protection, per-row logging, and a passing test suite.

This companion task doc tracks execution status for
[update_misa_requirements.md](./update_misa_requirements.md) and
[update_misa_design.md](./update_misa_design.md). Task checkboxes follow the
convention used in `ai/tfstate_backup_s3_implementaion/task_tfstate.md`
(`[ ]` not started, `[x]` done).

## 2. Problem Statement
Spend/Earn transactions currently only exist in the local `parsed_transaction_candidate`
table and must be manually re-entered into MISA Money Keeper. There is no
automated way to export them, since MISA does not expose a public API. This
task builds a Playwright-driven script that reads the qualifying rows and
enters them into MISA's web UI, safely and repeatably.

## 3. Scope
This task covers:
- Querying and classifying Spend/Earn rows from `parsed_transaction_candidate`.
- Mapping candidate fields to MISA's Amount/Account/Date/Category fields.
- Browser automation (login, Import button, popup form, Save) via Playwright.
- Local dedup state tracking across runs.
- Logging (per-row + summary) and a CLI runner.
- Unit tests and mocked-UI browser tests.

Out of scope: changes to the FastAPI app, the classifier/correlator pipeline,
or MISA account/category management.

## 4. Blocking Prerequisites
These must be resolved before Phase 2/4 tasks can be completed for real (they
can be stubbed/mocked until then):
1. Real selectors/HTML for the MISA login page, Import button, and popup form
   (requirements §3.3 / §10.1).
2. Confirmed date/time format expected by MISA's date field (requirements §10.2).
3. Confirmed presence/absence of 2FA/captcha on MISA login (requirements §10.3).
4. MISA test/sandbox credentials for manual verification (design §10).

## 5. Required Tasks

### 5.1 Data Layer [ ]
No browser or MISA dependency — can start immediately.

Required actions:
1. [ ] Add `app/misa/__init__.py` and `app/misa/models.py` with
   `MisaTransaction` (amount, account, datetime, category) and
   `MisaImportResult` (success, error_message) dataclasses.
2. [ ] Implement `app/misa/query.py`: SQLAlchemy query over
   `ParsedTransactionCandidate` (reusing `app/db/session.py`), plus
   `classify(row) -> Literal["Spend", "Earn", None]` using only
   `inferred_sender`/`inferred_receiver` vs `"Other"` (no `debit_credit`/
   `type_info`). Support optional `start_date`/`end_date` filtering on
   `datetime_sgt`.
3. [ ] Implement `app/misa/mapper.py`: `to_misa_transaction(row, classification)`
   per the field mapping table (Account = `inferred_sender` for Spend,
   `inferred_receiver` for Earn; `category` fixed to `"Bar & Coffee"`;
   datetime formatting isolated in one function, placeholder ISO format
   pending Blocking Prerequisite 2).
4. [ ] Implement `app/misa/dedup_store.py`: JSON store keyed by candidate `id`,
   with `is_imported(id)`, `mark_imported(id, metadata)`, atomic
   write-temp-then-rename save. Default path
   `ai/update_misa_implementation/imported_state.json`.
5. [ ] Add `tests/test_misa_query.py` covering the classification truth table
   (Spend, Earn, both-`"Other"` excluded, neither-`"Other"`/InternalTransfer
   excluded — confirmed against real data) and the field mapping for both a
   Spend row and an Earn row.
6. [ ] Add `tests/test_misa_dedup.py` covering: a fresh store treats all ids
   as not-imported; marking imported persists across reload; a failed
   attempt is never written so remains eligible for retry.

### 5.2 MISA Automation Layer [ ]
Required actions:
1. [ ] Add `playwright` to `requirements.txt`; document
   `playwright install chromium` as a setup step in README/Makefile.
2. [ ] Create `app/misa/selectors.py` with named placeholder constants for:
   login username/password inputs + submit button, Import button, popup
   amount/account/date/category fields, popup Save button, success indicator,
   error indicator. Fill in real values once Blocking Prerequisite 1 is
   available.
3. [ ] Implement `app/misa/client.py`:
   - `login(page, username, password)` with 2FA/captcha interactive fallback
     and `storage_state` persistence/reuse.
   - `add_transaction(page, tx: MisaTransaction) -> MisaImportResult` (click
     Import → fill popup → Save → detect success/error), wrapped so
     exceptions become a failed result instead of propagating.
4. [ ] Add test fixtures `tests/fixtures/misa_login.html` and
   `tests/fixtures/misa_transactions.html` mimicking the real MISA DOM closely
   enough to exercise the selectors in `selectors.py`.
5. [ ] Add Playwright tests `tests/test_misa_client.py`: login success/failure
   detection, `add_transaction` success/failure detection, and that one row's
   exception doesn't stop others.

### 5.3 Runner / CLI [ ]
Required actions:
1. [ ] Implement `app/misa/runner.py`: load dedup store → query + classify +
   map → filter already-imported → (if `--dry-run`, print planned imports and
   exit) → else launch Playwright, login, loop rows calling
   `add_transaction`, update dedup store on success, log per-row
   success/failure, print end-of-run summary (considered/imported/failed/
   skipped). CLI flags: `--start-date`, `--end-date`, `--state-file`,
   `--headed`, `--dry-run`.
2. [ ] Wire up logging (reuse `app/core/logging.py` if suitable, else a local
   `logging.basicConfig`) per the design's log line formats.
3. [ ] Add `.env` support for `MISA_USERNAME`/`MISA_PASSWORD` via
   `python-dotenv`; confirm `.env` and any `storage_state` session file are in
   `.gitignore`.

### 5.4 Verification [ ]
Required actions:
1. [ ] Run `--dry-run` against the real `data/txdb.sqlite3` to sanity-check
   classification/mapping output (182 Spend + 5 Earn rows expected per
   current data) before enabling real browser automation.
2. [ ] Manual test pass against a MISA sandbox/non-production account: verify
   one Spend row and one Earn row import with correct amount/account/date/
   category; verify re-run does not duplicate them.
3. [ ] Run the full test suite (`pytest tests/test_misa_*.py`) green.

## 6. Security Requirements
- MISA credentials must never be hardcoded or committed; load from
  `.env`/environment only.
- `.env` and any Playwright `storage_state` session file must be listed in
  `.gitignore`.
- No transaction data is sent anywhere except the user's own MISA account via
  their own authenticated browser session.

## 7. Acceptance Criteria
The task is complete when:
1. Running the script imports all not-yet-imported Spend/Earn rows from
   `txdb.sqlite3` into MISA via the web UI.
2. Each imported transaction in MISA shows the correct amount, account, date,
   and the fixed category `"Bar & Coffee"`.
3. Re-running the script does not re-import previously successful rows.
4. Console/log output clearly shows per-row success/failure and an
   end-of-run summary.
5. No MISA credentials are stored in the repository.
6. The test suite for `app/misa/` passes.

## 8. Suggested Next Steps
1. Start Data Layer tasks (§5.1) immediately — no MISA access required.
2. In parallel, resolve Blocking Prerequisites (§4) with the user/site
   inspection.
3. Start MISA Automation Layer tasks (§5.2) once selectors are available
   (placeholders can be scaffolded early, but client tests need real-enough
   fixtures to be meaningful).
4. Implement Runner/CLI (§5.3) once §5.1 is done; stub `client.py` calls until
   §5.2 is ready.
5. Finish with Verification (§5.4), ending with a manual sandbox run before
   any production import run.
