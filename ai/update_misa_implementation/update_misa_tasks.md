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
     exceptions become a failed result instead of propagating. **Still
     incomplete (2026-08-07)**: always uses Spend-tab selectors regardless
     of `tx`'s classification (no tab click / no Spend-vs-Earn selector
     switch); fills category via `fill()` only without also clicking the
     matching dropdown option (confirmed required to actually commit the
     selection); and uses `POPUP_SAVE_AND_ADD_BUTTON`, which leaves the
     popup open in "add another" mode rather than closing it. These three
     gaps must be closed before `add_transaction()` can be used for a real
     per-row import loop (see design §12 item 4).
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
   category; verify re-run does not duplicate them. **Partial/ad-hoc
   progress (2026-08-07)**: no sandbox account exists, so this was done
   directly against the real/production account via standalone manual
   scripts (not the real runner/`add_transaction()` flow, since that's
   still incomplete — see §5.2 item 3). Spend-tab field fill confirmed
   correct without clicking Save. Earn-tab flow was run all the way
   through Save and **did create a real transaction** (amount 10, account
   "Helper", category "Balance") — not yet cleaned up. This also revealed
   `POPUP_SAVE_AND_ADD_BUTTON` doesn't close the popup (Save & Add Another
   behavior), so the real runner still needs the Save & Close button
   before this step can be considered done via the actual `add_transaction()`
   code path.
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
