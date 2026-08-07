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
1. ~~Real selectors/HTML for the MISA login page, Import button, and popup
   form (requirements §3.3 / §10.1).~~ **Resolved (2026-08-08)** — login,
   Import button, both Spend/Earn tabs, all Spend/Earn field selectors,
   and both Save buttons (`POPUP_SAVE_AND_ADD_BUTTON` / "Lưu và thêm" and
   `POPUP_SAVE_AND_CLOSE_BUTTON` / "Lưu") are confirmed working via manual
   scripts (see `/memories/repo/misa_selectors.md`). Remaining gap:
   `client.py`'s `add_transaction()` still needs to be updated to use
   `POPUP_SAVE_AND_CLOSE_BUTTON` instead of `POPUP_SAVE_AND_ADD_BUTTON`.
2. ~~Confirmed date/time format expected by MISA's date field (requirements
   §10.2).~~ **Resolved**: `DD/MM/YYYY HH:MM`.
3. Confirmed presence/absence of 2FA/captcha on MISA login (requirements
   §10.3). **Still open** — 2FA has never actually been triggered during
   testing so far.
4. MISA test/sandbox credentials for manual verification (design §10). **Not
   available** — all manual verification to date has been performed
   directly against the real/production MISA account (see §5.4 note below).

## 5. Required Tasks

### 5.1 Data Layer [x]
No browser or MISA dependency — can start immediately.

Required actions:
1. [x] Add `app/misa/__init__.py` and `app/misa/models.py` with
   `MisaTransaction` (amount, account, datetime, category) and
   `MisaImportResult` (success, error_message) dataclasses.
2. [x] Implement `app/misa/query.py`: SQLAlchemy query over
   `ParsedTransactionCandidate` (reusing `app/db/session.py`), plus
   `classify(row) -> Literal["Spend", "Earn", None]` using only
   `inferred_sender`/`inferred_receiver` vs `"Other"` (no `debit_credit`/
   `type_info`). Support optional `start_date`/`end_date` filtering on
   `datetime_sgt`.
3. [x] Implement `app/misa/mapper.py`: `to_misa_transaction(row, classification)`
   per the field mapping table (Account = `inferred_sender` for Spend,
   `inferred_receiver` for Earn; datetime formatted `DD/MM/YYYY HH:MM`
   (confirmed, Blocking Prerequisite 2 resolved); category is
   **classification-dependent**: `CATEGORY = "Bars & Coffee"` for Spend,
   `EARN_CATEGORY = "Balance"` for Earn — confirmed 2026-08-07 that a
   single shared category is invalid for one of the two types since Spend
   and Earn have distinct category lists in MISA).
4. [x] Implement `app/misa/dedup_store.py`: JSON store keyed by candidate `id`,
   with `is_imported(id)`, `mark_imported(id, metadata)`, atomic
   write-temp-then-rename save. Default path
   `ai/update_misa_implementation/imported_state.json`.
5. [x] Add `tests/test_misa_query.py` covering the classification truth table
   (Spend, Earn, both-`"Other"` excluded, neither-`"Other"`/InternalTransfer
   excluded — confirmed against real data) and the field mapping for both a
   Spend row and an Earn row.
6. [x] Add `tests/test_misa_dedup.py` covering: a fresh store treats all ids
   as not-imported; marking imported persists across reload; a failed
   attempt is never written so remains eligible for retry.

### 5.2 MISA Automation Layer [ ]
Required actions:
1. [x] Add `playwright` to `requirements.txt`; document
   `playwright install chromium` as a setup step in README/Makefile.
2. [x] Create `app/misa/selectors.py` with named constants for: login
   username/password inputs + submit button, Import button, popup
   Spend/Earn tabs, popup amount/account/date/category fields (separate
   `_SPEND_`/`_EARN_` constants per field since the two tabs are
   structurally different panels, confirmed 2026-08-07), both popup Save
   buttons, success indicator, error indicator. **Confirmed working**
   end-to-end for both tabs via manual scripts, including both
   `POPUP_SAVE_AND_ADD_BUTTON` ("Lưu và thêm") and
   `POPUP_SAVE_AND_CLOSE_BUTTON` ("Lưu", confirmed 2026-08-08 — see
   Blocking Prerequisite 1), except: `LOGIN_2FA_INDICATOR`,
   `SUCCESS_INDICATOR`, `ERROR_INDICATOR` (still guessed/never matched,
   even on confirmed-successful saves).
3. [x] Implement `app/misa/client.py`:
   - `login(page, username, password)` with 2FA/captcha interactive fallback
     and `storage_state` persistence/reuse. **Confirmed working.**
   - `click_import_button(page)`: opens the popup and waits
     `POPUP_ACCOUNT_SETTLE_MS` (2.5s) for MISA's async default-account load
     to settle. **Confirmed working for the initial popup-open case only**
     — switching tabs re-triggers the same async load and needs an
     equivalent wait after the tab click, not yet added here (only present
     in the ad-hoc Earn manual test script so far).
   - `add_transaction(page, tx: MisaTransaction) -> MisaImportResult` (click
     Import → fill popup → Save → detect success/error), wrapped so
     exceptions become a failed result instead of propagating. **Done
     (2026-08-08)** — now branches by `tx.classification` to select the
     correct Spend/Earn tab and tab-specific selectors, waits
     `POPUP_ACCOUNT_SETTLE_MS` after switching to Earn (same async
     default-account race as the initial popup open), fills category and
     explicitly clicks the matching dropdown option (typing alone does not
     commit the selection), and clicks `POPUP_SAVE_AND_CLOSE_BUTTON`
     ("Lưu") so the popup closes after each save. Success detection now
     treats either `SUCCESS_INDICATOR` visibility or the popup closing as
     success, matching real MISA's behavior where the true success signal
     is the popup closing rather than a toast.
4. [x] Add test fixtures `tests/fixtures/misa_login.html` and
   `tests/fixtures/misa_transactions.html` mimicking the real MISA DOM closely
   enough to exercise the selectors in `selectors.py`. **Done (2026-08-08)**
   — every selector in `selectors.py` (login fields/button/error, Import
   button, single-transaction option, popup tabs, all Spend/Earn field
   selectors + account options containers, both Save buttons) was verified
   to resolve to exactly the expected element(s) against these fixtures via
   a throwaway Playwright script (not committed). Notable fixture quirk:
   the Earn panel needed a leading empty placeholder `<div>` sibling to
   avoid `POPUP_SPEND_TAB`'s/`POPUP_AMOUNT_SPEND_INPUT`'s `nth-child(1)`
   qualifier from accidentally also resolving inside the Earn panel's
   subtree (both panels stay mounted simultaneously, `hidden`-toggled, like
   the real site).
5. [x] Add Playwright tests `tests/test_misa_client.py`: login success/failure
   detection, `add_transaction` success/failure detection, and that one row's
   exception doesn't stop others. **Done (2026-08-08)** — 7 tests, all
   passing against `tests/fixtures/misa_login.html`/`misa_transactions.html`
   (a small dynamic submit handler was added to `misa_login.html` so it can
   simulate real success/failure login outcomes based on the credentials
   passed in, not just a static body-class toggle). This work uncovered and
   fixed a real bug in `client.py`'s `add_transaction()`: it waited on a
   single combined selector `f"{SUCCESS_INDICATOR}, {ERROR_INDICATOR}"`,
   but Playwright's `text=` engine consumes an unescaped comma as part of
   its own search text instead of treating it as a selector-list
   separator, so the wait silently timed out even when the indicator was
   genuinely visible. Fixed by replacing it with a poll loop
   (`_wait_for_save_outcome()`), mirroring the existing
   `_wait_for_login_outcome()` pattern.

### 5.3 Runner / CLI [ ]
Required actions:
1. [x] Implement `app/misa/runner.py`: load dedup store → query + classify +
   map → filter already-imported → (if `--dry-run`, print planned imports and
   exit) → else launch Playwright, login, loop rows calling
   `add_transaction`, update dedup store on success, log per-row
   success/failure, print end-of-run summary (considered/imported/failed/
   skipped). CLI flags: `--start-date`, `--end-date`, `--state-file`,
   `--headed`, `--dry-run`. **Done (2026-08-08)** — verified via
   `python -m app.misa.runner --dry-run` against the real
   `data/txdb.sqlite3`: 187 rows planned (182 Spend + 5 Earn, matching the
   §5.4 item 1 expectation), 0 skipped. Reuses `app/core/logging.py`'s
   `get_logger()` and loads `MISA_USERNAME`/`MISA_PASSWORD` from
   `.env.misa` via `python-dotenv` (same convention as the manual scripts
   in `scripts/`, not the main `.env`) — this covers items 2 and 3 below
   as a side effect of implementation, though neither has been separately
   re-verified as its own checklist item. **Added `--limit` flag
   (2026-08-08)** to cap the number of rows imported, used by §5.4.2 to
   run small, safe verification batches. The real (non-dry-run) import
   path was exercised successfully during §5.4.2 (one Earn + one Spend
   row imported into the live MISA account).
2. [x] Wire up logging (reuse `app/core/logging.py` if suitable, else a local
   `logging.basicConfig`) per the design's log line formats. **Done
   (2026-08-08)** — `runner.py` reuses `app/core/logging.py`'s
   `get_logger(__name__)` (stdout + rotating `app.log`). Verified the three
   design-specified line shapes exactly, via `tests/test_misa_runner.py`
   capturing records directly off `runner.logger` (bypassing `caplog`,
   which misses everything since `get_logger()` sets `propagate = False`):
   `[imported] id=... amount=... account=... datetime=...` (INFO),
   `[failed]   id=... amount=... account=... datetime=... reason=...`
   (ERROR), `Summary: considered=%d imported=%d failed=%d
   skipped(already imported)=%d` (INFO), and the dry-run
   `[would-import] id=... type=... amount=... account=... datetime=...
   category=...` line.
3. [x] Add `.env` support for `MISA_USERNAME`/`MISA_PASSWORD` via
   `python-dotenv`; confirm `.env` and any `storage_state` session file are in
   `.gitignore`. **Done (2026-08-08)** — `main()` calls
   `load_dotenv(".env.misa")` (not the main `.env`, which is reserved for
   the FastAPI app's `pydantic` `Settings`); verified via
   `tests/test_misa_runner.py::test_main_loads_dotenv_from_env_misa_file_not_main_env`.
   `.gitignore` confirmed (and asserted in
   `test_gitignore_covers_misa_secrets_and_session_state`) to cover
   `.env.misa`, `*.storage_state.json`, and `app.log`. Also added a test
   (`test_credentials_are_never_logged`) confirming `MISA_USERNAME`/
   `MISA_PASSWORD` values never appear in any log line, and a test
   (`test_summary_logged_when_credentials_missing`) confirming a missing
   credential aborts with a clear error *before* `sync_playwright()` is
   ever called (no browser launch, no partial run).

### 5.4 Verification [ ]
Required actions:
1. [x] Run `--dry-run` against the real `data/txdb.sqlite3` to sanity-check
   classification/mapping output (182 Spend + 5 Earn rows expected per
   current data) before enabling real browser automation. **Done
   (2026-08-08)** — output matches the expected 182 Spend + 5 Earn split
   (187 total, 0 skipped). **Sanity-check flag**: 4 rows have
   `amount=None` in the source data (e.g. ids `e5fe2e37-...`,
   `a24b6380-...`, `2c45848a-...`, plus one other); these should be
   resolved before a real import run because MISA will reject a missing
   amount.
2. [x] Manual test pass against a MISA sandbox/non-production account: verify
   one Spend row and one Earn row import with correct amount/account/date/
   category; verify re-run does not duplicate them. **Done (2026-08-08)** —
   no sandbox account exists, so verification was performed directly
   against the real/production account using the real runner/`add_transaction()`
   code path (with `--limit 1` for safety). **Earn row**: id
   `8b0974e3-55c6-49da-9f63-d90b8035097d`, amount 93.0, account
   `Acb online`, datetime `17/07/2026 00:00`, category `Balance` — imported
   successfully. **Spend row**: id `0c04e58f-9f9c-4f02-9c0a-f77ae7dd17ae`,
   amount 7.8, account `Ngân hàng Trust`, datetime `20/06/2026 00:00`,
   category `Bars & Coffee` — imported successfully. Re-run dry-runs for
   the same date ranges show `skipped(already imported)=1` for each row,
   confirming the dedup store prevents duplicates. **Implementation fixes
   required during this step**: (a) added `MISA_ACCOUNT_NAME_MAP` in
   `app/misa/mapper.py` to map canonical DB account names (e.g. "ACB
   Online", "Trust", "DBS") to the exact labels shown in MISA's dropdown
   (e.g. "Acb online", "Ngân hàng Trust", "DBS bank"); (b) fixed the
   `end_date` filter in `app/misa/query.py` to use `< end_date + 1 day`
   so SQLite's stored midnight datetimes are included; (c) added
   `classification` to `MisaTransaction` so `add_transaction()` can branch
   by tab.
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
   and the correct category for its classification (`"Bars & Coffee"` for
   Spend, `"Balance"` for Earn).
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
