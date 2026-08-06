"""Named selector constants for the MISA Money Keeper web UI.

All Playwright selectors used by `app/misa/client.py` must be defined here —
no other module should hardcode a selector string. This keeps selector
maintenance isolated to one place when MISA's DOM changes.

Placeholder values below are TODOs pending manual inspection of the real
MISA pages (see ai/update_misa_implementation/update_misa_tasks.md
Blocking Prerequisite 1). Replace each placeholder with the real selector,
then remove its `# TODO` comment.

Selector convention: prefer a real `id`/`data-testid` attribute or unique
visible text over deep/fragile CSS paths.
"""

# --- URLs -------------------------------------------------------------
LOGIN_URL = "https://moneykeeperapp.misa.vn/"
TRANSACTIONS_URL = "https://moneykeeperapp.misa.vn/management/transactions"

# --- Login page ---------------------------------------------------------
LOGIN_USERNAME_INPUT = "#username input"
LOGIN_PASSWORD_INPUT = "#password input"
LOGIN_SUBMIT_BUTTON = "#app > div:nth-child(1) > div.content-full > div > div.content-signin > div.content-right > div.content-form > button"

# Element(s) that indicate login succeeded, e.g. a nav item only shown when
# authenticated, or simply the transactions page URL/heading loading.
LOGIN_SUCCESS_INDICATOR = "#app-container > div.nav-container.flex.justify-between > div > div.ctn-nav-left.flex.align-items-center > p > span"

# Element that indicates login failed (e.g. an inline validation/error
# message on the login form).
LOGIN_ERROR_INDICATOR = "#app > div:nth-child(1) > div.content-full > div > div.content-signin > div.content-right > div.content-form > div.error-message"

# Element(s) whose presence signals a 2FA/captcha challenge that cannot be
# automated and requires falling back to interactive/headed login.
LOGIN_2FA_INDICATOR = "text=Verification code"  # TODO: confirm real selector

# --- Transactions page ---------------------------------------------------
IMPORT_BUTTON = "text=Import"  # TODO: confirm real selector

# --- Add-transaction popup ------------------------------------------------
POPUP_AMOUNT_INPUT = "#popup-amount"  # TODO: confirm real selector
POPUP_ACCOUNT_INPUT = "#popup-account"  # TODO: confirm real selector
POPUP_DATE_INPUT = "#popup-date"  # TODO: confirm real selector
POPUP_CATEGORY_INPUT = "#popup-category"  # TODO: confirm real selector
POPUP_SAVE_BUTTON = "#popup-save"  # TODO: confirm real selector

# Element(s) indicating the popup save succeeded (e.g. a success toast, or
# the popup closing and the new row appearing in the list).
SUCCESS_INDICATOR = "text=Saved successfully"  # TODO: confirm real selector

# Element(s) indicating the popup save failed (e.g. a validation error
# message within the popup).
ERROR_INDICATOR = ".popup-error-message"  # TODO: confirm real selector
