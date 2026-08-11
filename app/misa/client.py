"""Playwright client for MISA Money Keeper: login and per-transaction import.

See ai/update_misa_implementation/update_misa_design.md §5.2 for the intended
behavior of each function.
"""

import logging
from pathlib import Path
from typing import TYPE_CHECKING, NamedTuple, Optional, Union

from app.misa import selectors
from app.misa.models import MisaImportResult, MisaTransaction

if TYPE_CHECKING:
    from playwright.sync_api import BrowserContext, Page

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


def is_logged_in(page: "Page") -> bool:
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


def _wait_for_login_outcome(page: "Page", timeout_ms: int) -> bool:
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


def _wait_for_save_outcome(page: "Page", popup_locator, timeout_ms: int) -> Optional[bool]:
    """Poll for a save outcome after clicking the Save & Close button.

    Treats any of the following as success:
      - `SUCCESS_INDICATOR` becomes visible (matches the test fixture),
      - the Add Transaction popup closes (real MISA's actual success
        signal, since no toast/indicator has been confirmed to match).

    Treats `ERROR_INDICATOR` becoming visible as an error.

    Returns True on success, False on error, or None on timeout. Deliberately
    does NOT use a single combined `wait_for_selector(f"{a}, {b}")` call:
    Playwright's `text=` engine consumes an unescaped comma as part of its
    own search text rather than treating it as a selector-list separator, so
    a combined selector built from an unquoted `text=...` indicator silently
    never matches even when the indicator is genuinely visible (reproduced
    via tests/test_misa_client.py against tests/fixtures/misa_transactions.html).
    Polling each locator individually (same pattern as `_wait_for_login_outcome`)
    avoids this pitfall.
    """
    success_locator = page.locator(selectors.SUCCESS_INDICATOR)
    error_locator = page.locator(selectors.ERROR_INDICATOR)
    poll_interval_ms = 250
    elapsed_ms = 0
    while elapsed_ms <= timeout_ms:
        if success_locator.is_visible():
            return True
        if not popup_locator.is_visible():
            return True
        if error_locator.is_visible():
            return False
        page.wait_for_timeout(poll_interval_ms)
        elapsed_ms += poll_interval_ms
    return None


def login(page: "Page", username: str, password: str) -> bool:
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


def save_session(context: "BrowserContext", path: Union[str, Path] = DEFAULT_STORAGE_STATE_PATH) -> None:
    """Persist the browser context's storage_state (cookies/local storage)
    to `path` for reuse on the next run."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    context.storage_state(path=str(path))


def click_import_button(page: "Page", timeout_ms: int = POPUP_TIMEOUT_MS) -> bool:
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


class _TabSelectors(NamedTuple):
    """Selector bundle for one popup tab (Spend or Earn)."""

    tab: str
    amount_input: str
    account_input: str
    account_options_container: str
    date_input: str
    category_input: str


_SPEND_SELECTORS = _TabSelectors(
    tab=selectors.POPUP_SPEND_TAB,
    amount_input=selectors.POPUP_AMOUNT_SPEND_INPUT,
    account_input=selectors.POPUP_ACCOUNT_SPEND_INPUT,
    account_options_container=selectors.POPUP_ACCOUNT_SPEND_OPTIONS_CONTAINER,
    date_input=selectors.POPUP_DATE_SPEND_INPUT,
    category_input=selectors.POPUP_CATEGORY_SPEND_INPUT,
)

_EARN_SELECTORS = _TabSelectors(
    tab=selectors.POPUP_EARN_TAB,
    amount_input=selectors.POPUP_AMOUNT_EARN_INPUT,
    account_input=selectors.POPUP_ACCOUNT_EARN_INPUT,
    account_options_container=selectors.POPUP_ACCOUNT_EARN_OPTIONS_CONTAINER,
    date_input=selectors.POPUP_DATE_EARN_INPUT,
    category_input=selectors.POPUP_CATEGORY_EARN_INPUT,
)


def _tab_selectors(classification: str) -> _TabSelectors:
    if classification == "Earn":
        return _EARN_SELECTORS
    return _SPEND_SELECTORS


def select_account(
    page: "Page",
    account_name: str,
    account_input: str,
    account_options_container: str,
    timeout_ms: int = POPUP_TIMEOUT_MS,
) -> bool:
    """Select `account_name` in the popup's Account dropdown.

    The account field is a custom dropdown, not a fillable text field: this
    clicks `account_input` to open the options list, waits for
    `account_options_container` to appear, then clicks the option whose text
    matches `account_name` (e.g. "PayLah", "DBS" — comes from the row's data,
    not a fixed selector).

    Returns True if the option was clicked, False otherwise. Never raises.
    """
    try:
        page.click(account_input)
        page.wait_for_selector(account_options_container, timeout=timeout_ms)
        page.click(selectors.account_option_selector(account_name, container=account_options_container))
        return True
    except Exception as exc:
        logger.error("Selecting account %r failed: %s", account_name, exc)
        return False


def _select_category(
    page: "Page", category_name: str, category_input: str, timeout_ms: int = POPUP_TIMEOUT_MS
) -> bool:
    """Fill and commit `category_name` in the popup's Category dropdown.

    MISA's category field only filters the dropdown when typed into; the
    matching option must be explicitly clicked to commit the selection,
    otherwise Save is blocked by validation (red border, popup stays open).
    """
    try:
        page.fill(category_input, category_name)
        page.click(f'{selectors.IMPORT_BUTTON_RESULT} >> text="{category_name}"')
        return True
    except Exception as exc:
        logger.error("Selecting category %r failed: %s", category_name, exc)
        return False


def _fill_date(page: "Page", date_input: str, date_value: str) -> None:
    """Fill MISA's custom datepicker field and ensure the value sticks.

    MISA's datepicker is a Vue-controlled component with two sibling inputs
    (date-only and datetime). Direct Playwright `fill()`/typing is ignored
    or reset to the current datetime by the component. This helper targets
    the datetime input by its placeholder and sets the value via JavaScript,
    dispatching focus/input/change/blur events so Vue picks up the value.
    """
    datetime_selector = f'{date_input}[placeholder="dd/mm/yyyy hh:mm"]'
    locator = page.locator(datetime_selector)
    effective_selector = datetime_selector
    if locator.count() == 0:
        # Fallback to the original selector if the placeholder is different
        # (e.g. in test fixtures that do not include placeholder attrs).
        locator = page.locator(date_input)
        effective_selector = date_input

    # Set value via JS and dispatch events so Vue/React bindings pick it up.
    # We skip locator.focus() because the element may be hidden in fixtures or
    # not considered actionable by Playwright's actionability checks.
    page.evaluate(
        """
        ([selector, value]) => {
            const el = document.querySelector(selector);
            if (!el) return;
            el.value = value;
            ['focus', 'input', 'change', 'blur'].forEach((name) => {
                el.dispatchEvent(new Event(name, { bubbles: true }));
            });
        }
        """,
        [effective_selector, date_value],
    )
    page.wait_for_timeout(250)


def add_transaction(page: "Page", tx: MisaTransaction) -> MisaImportResult:
    """Add one transaction to MISA via the Import popup flow.

    Clicks the Import button, selects the Spend or Earn tab, fills
    Amount/Account/Date/Category, clicks Save & Close, then waits for the
    popup to close or an error indicator to appear. Any exception (timeout,
    selector not found, etc.) is caught and converted into a failed
    `MisaImportResult` instead of propagating, so a single row's failure does
    not stop the caller's loop over other rows.
    """
    try:
        if not click_import_button(page):
            return MisaImportResult(success=False, error_message="Import popup did not open")

        tab = _tab_selectors(tx.classification)

        page.click(tab.tab)
        # Switching to the Earn tab re-triggers MISA's async default-account
        # load for that panel; wait for it to settle before touching the
        # account field, otherwise the selection gets silently reverted.
        if tx.classification == "Earn":
            page.wait_for_timeout(POPUP_ACCOUNT_SETTLE_MS)

        page.wait_for_selector(tab.amount_input, timeout=POPUP_TIMEOUT_MS)

        page.fill(tab.amount_input, str(tx.amount))
        if not select_account(page, tx.account, tab.account_input, tab.account_options_container):
            return MisaImportResult(
                success=False, error_message=f"Could not select account {tx.account!r}"
            )
        _fill_date(page, tab.date_input, tx.datetime)
        if not _select_category(page, tx.category, tab.category_input):
            return MisaImportResult(
                success=False, error_message=f"Could not select category {tx.category!r}"
            )

        popup_locator = page.locator(selectors.IMPORT_BUTTON_RESULT)
        page.click(selectors.POPUP_SAVE_AND_CLOSE_BUTTON)

        outcome = _wait_for_save_outcome(page, popup_locator, POPUP_TIMEOUT_MS)
        if outcome is True:
            return MisaImportResult(success=True)
        if outcome is False:
            error_message = page.locator(selectors.ERROR_INDICATOR).inner_text()
            return MisaImportResult(success=False, error_message=error_message)
        return MisaImportResult(success=False, error_message="No success/error indicator appeared")
    except Exception as exc:
        return MisaImportResult(success=False, error_message=str(exc))
