"""Playwright client for MISA Money Keeper: login and per-transaction import.

See ai/update_misa_implementation/update_misa_design.md §5.2 for the intended
behavior of each function.
"""

import logging
from pathlib import Path
from typing import Optional, Union

from playwright.sync_api import BrowserContext, Page

from app.misa import selectors
from app.misa.models import MisaImportResult, MisaTransaction

logger = logging.getLogger(__name__)

DEFAULT_STORAGE_STATE_PATH = "ai/update_misa_implementation/misa.storage_state.json"

LOGIN_TIMEOUT_MS = 15_000
INTERACTIVE_LOGIN_TIMEOUT_MS = 120_000
POPUP_TIMEOUT_MS = 10_000

# The popup asynchronously loads/sets a default account shortly after
# opening; if the account field is touched before this settles, the
# default overwrites whatever account was selected. Wait this long after
# the popup opens before interacting with the account field.
POPUP_ACCOUNT_SETTLE_MS = 2_500


def is_logged_in(page: Page) -> bool:
    """Check whether `page` is currently on an authenticated MISA session.

    Navigates to the transactions page and checks for the success indicator
    (used to validate a restored `storage_state` before falling back to a
    fresh login).
    """
    page.goto(selectors.TRANSACTIONS_URL)
    try:
        page.wait_for_selector(selectors.LOGIN_SUCCESS_INDICATOR, timeout=LOGIN_TIMEOUT_MS)
        return True
    except Exception:
        return False


def _wait_for_login_outcome(page: Page, timeout_ms: int) -> bool:
    """Poll for either the success or error indicator, whichever appears
    first, up to `timeout_ms`. Returns True on success, False on error or
    timeout (neither indicator ever appeared)."""
    poll_interval_ms = 250
    elapsed_ms = 0
    while elapsed_ms <= timeout_ms:
        if page.locator(selectors.LOGIN_SUCCESS_INDICATOR).is_visible():
            return True
        if page.locator(selectors.LOGIN_ERROR_INDICATOR).is_visible():
            return False
        page.wait_for_timeout(poll_interval_ms)
        elapsed_ms += poll_interval_ms
    return False


def login(page: Page, username: str, password: str) -> bool:
    """Log into MISA Money Keeper.

    Fills the username/password fields and submits. If a 2FA/captcha
    challenge is detected, falls back to an interactive wait — the caller is
    expected to have launched a headed browser so the user can complete the
    challenge manually within `INTERACTIVE_LOGIN_TIMEOUT_MS`.

    Returns True if login succeeded (`LOGIN_SUCCESS_INDICATOR` became
    visible before `LOGIN_ERROR_INDICATOR` or the timeout), False otherwise.
    Never raises for expected failure modes (bad credentials, timeout) —
    those are reported via the return value.
    """
    try:
        page.goto(selectors.LOGIN_URL)
        page.fill(selectors.LOGIN_USERNAME_INPUT, username)
        page.fill(selectors.LOGIN_PASSWORD_INPUT, password)
        page.click(selectors.LOGIN_SUBMIT_BUTTON)

        if page.locator(selectors.LOGIN_2FA_INDICATOR).is_visible():
            logger.info(
                "2FA/captcha challenge detected; waiting up to %ss for "
                "interactive completion in the browser window...",
                INTERACTIVE_LOGIN_TIMEOUT_MS // 1000,
            )
            return _wait_for_login_outcome(page, INTERACTIVE_LOGIN_TIMEOUT_MS)

        return _wait_for_login_outcome(page, LOGIN_TIMEOUT_MS)
    except Exception as exc:
        logger.error("Login failed: %s", exc)
        return False


def save_session(context: BrowserContext, path: Union[str, Path] = DEFAULT_STORAGE_STATE_PATH) -> None:
    """Persist the browser context's storage_state (cookies/local storage)
    to `path` for reuse on the next run."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    context.storage_state(path=str(path))


def click_import_button(page: Page, timeout_ms: int = POPUP_TIMEOUT_MS) -> bool:
    """Open the Add Transaction popup for a single transaction.

    `IMPORT_BUTTON` is an up/down dropdown toggle: clicking it reveals more
    options, one of which (`SINGLE_TRANSACTION_OPTION`) opens the Add
    Transaction popup for a single transaction. This clicks both in
    sequence, then waits for the popup to open (confirmed via
    `IMPORT_BUTTON_RESULT`).

    Returns True if the popup opened, False otherwise. Never raises.
    """
    try:
        page.click(selectors.IMPORT_BUTTON)
        page.click(selectors.SINGLE_TRANSACTION_OPTION)
        page.wait_for_selector(selectors.IMPORT_BUTTON_RESULT, timeout=timeout_ms)
        page.wait_for_timeout(POPUP_ACCOUNT_SETTLE_MS)
        return True
    except Exception as exc:
        logger.error("Clicking Import button failed: %s", exc)
        return False


def select_account(page: Page, account_name: str, timeout_ms: int = POPUP_TIMEOUT_MS) -> bool:
    """Select `account_name` in the popup's Account dropdown.

    `POPUP_ACCOUNT_SPEND_INPUT` is a dropdown button, not a fillable field:
    this clicks it to open the options list, waits for the list to appear,
    then clicks the option whose text matches `account_name` (e.g.
    "PayLah", "DBS" — comes from the row's data, not a fixed selector).

    Returns True if the option was clicked, False otherwise. Never raises.
    """
    try:
        page.click(selectors.POPUP_ACCOUNT_SPEND_INPUT)
        page.wait_for_selector(selectors.POPUP_ACCOUNT_SPEND_OPTIONS_CONTAINER, timeout=timeout_ms)
        page.click(selectors.account_option_selector(account_name))
        return True
    except Exception as exc:
        logger.error("Selecting account %r failed: %s", account_name, exc)
        return False


def add_transaction(page: Page, tx: MisaTransaction) -> MisaImportResult:
    """Add one transaction to MISA via the Import popup flow.

    Clicks the Import button, fills Amount/Account/Date/Category, clicks
    Save, then waits for either the success or error indicator. Any
    exception (timeout, selector not found, etc.) is caught and converted
    into a failed `MisaImportResult` instead of propagating, so a single
    row's failure does not stop the caller's loop over other rows.
    """
    try:
        if not click_import_button(page):
            return MisaImportResult(success=False, error_message="Import popup did not open")

        page.wait_for_selector(selectors.POPUP_AMOUNT_SPEND_INPUT, timeout=POPUP_TIMEOUT_MS)

        page.fill(selectors.POPUP_AMOUNT_SPEND_INPUT, str(tx.amount))
        if not select_account(page, tx.account):
            return MisaImportResult(
                success=False, error_message=f"Could not select account {tx.account!r}"
            )
        page.fill(selectors.POPUP_DATE_SPEND_INPUT, tx.datetime)
        page.fill(selectors.POPUP_CATEGORY_SPEND_INPUT, tx.category)

        page.click(selectors.POPUP_SAVE_AND_ADD_BUTTON)

        success_locator = page.locator(selectors.SUCCESS_INDICATOR)
        error_locator = page.locator(selectors.ERROR_INDICATOR)
        page.wait_for_selector(
            f"{selectors.SUCCESS_INDICATOR}, {selectors.ERROR_INDICATOR}",
            timeout=POPUP_TIMEOUT_MS,
        )

        if error_locator.is_visible():
            return MisaImportResult(success=False, error_message=error_locator.inner_text())
        if success_locator.is_visible():
            return MisaImportResult(success=True)
        return MisaImportResult(success=False, error_message="No success/error indicator appeared")
    except Exception as exc:
        return MisaImportResult(success=False, error_message=str(exc))
