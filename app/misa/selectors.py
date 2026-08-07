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
IMPORT_BUTTON = "#app-container > div.app-container > div.sidebar-container.expand-sidebar > div.ctn-top > div > div:nth-child(5) > div > div > div > div > div.menu-item-updown.op-icon-chevron-down"  # TODO: confirm real selector

SINGLE_TRANSACTION_OPTION = "#app-container > div.app-container > div.sidebar-container.expand-sidebar > div.ctn-top > div > div:nth-child(5) > div > div > div:nth-child(2) > div:nth-child(1) > div"

# --- Add-transaction popup ------------------------------------------------
# Modal container that appears after clicking IMPORT_BUTTON; its presence
# confirms the Add Transaction popup actually opened.
IMPORT_BUTTON_RESULT = "#app > div.modals-container > div > div.vfm__container.vfm--absolute.vfm--inset.vfm--outline-none.modal-container.null > div > div.modal__content.flex-column.flex1"

# Tabs within the popup selecting the transaction type; must be clicked
# before filling the rest of the form, per the row's classification
# ("Spend" -> POPUP_SPEND_TAB, "Earn" -> POPUP_EARN_TAB).
POPUP_SPEND_TAB = "#app > div.modals-container > div > div.vfm__container.vfm--absolute.vfm--inset.vfm--outline-none.modal-container.null > div > div.modal__content.flex-column.flex1 > div > div > div.flex.tab-header > div > div > div > div.ms-tab.tabActived"  # TODO: confirm real selector
POPUP_EARN_TAB = "#app > div.modals-container > div > div.vfm__container.vfm--absolute.vfm--inset.vfm--outline-none.modal-container.null > div > div.modal__content.flex-column.flex1 > div > div > div.flex.tab-header > div > div > div > div:nth-child(2)"  # TODO: confirm real selector

POPUP_AMOUNT_SPEND_INPUT = "#app > div.modals-container > div > div.vfm__container.vfm--absolute.vfm--inset.vfm--outline-none.modal-container.null > div > div.modal__content.flex-column.flex1 > div > div > div.list-tab > div > div > div > div > div:nth-child(1) > div.left > div:nth-child(1) > div.p-t-8 > div > div input"

# Dummy placeholder guessed from the Spend tab's structure (assumes the
# Earn tab is the 2nd tab-panel under list-tab). Unconfirmed - needs real
# DOM inspection once POPUP_EARN_TAB is fixed and actually switches tabs.
POPUP_AMOUNT_EARN_INPUT = "#app > div.modals-container > div > div.vfm__container.vfm--absolute.vfm--inset.vfm--outline-none.modal-container.null > div > div.modal__content.flex-column.flex1 > div > div > div.list-tab > div:nth-child(2) > div > div > div > div > div.left > div:nth-child(1) > div.p-t-8 > div input"

# Account is a custom dropdown, not a fillable text field: click
# POPUP_ACCOUNT_SPEND_INPUT to open the options list, wait for
# POPUP_ACCOUNT_SPEND_OPTIONS_CONTAINER to appear, then click the option
# matching the row's account name via account_option_selector() (the value
# comes from the DB — inferred_sender/inferred_receiver — so there's no
# single fixed selector for "the" account option).
POPUP_ACCOUNT_SPEND_INPUT = "#app > div.modals-container > div > div.vfm__container.vfm--absolute.vfm--inset.vfm--outline-none.modal-container.null > div > div.modal__content.flex-column.flex1 > div > div > div.list-tab > div > div > div > div > div:nth-child(1) > div.left > div:nth-child(2) > div.p-t-8 > div > div.input-container > input"
POPUP_ACCOUNT_SPEND_OPTIONS_CONTAINER = "#app > div.modals-container > div > div.vfm__container.vfm--absolute.vfm--inset.vfm--outline-none.modal-container.null > div > div.modal__content.flex-column.flex1 > div > div > div.list-tab > div > div > div > div > div:nth-child(1) > div.left > div:nth-child(2) > div.p-t-8 > div > div.dropdown-container > div"

# Dummy placeholders guessed from the Spend tab's structure - unconfirmed.
POPUP_ACCOUNT_EARN_INPUT = "#app > div.modals-container > div > div.vfm__container.vfm--absolute.vfm--inset.vfm--outline-none.modal-container.null > div > div.modal__content.flex-column.flex1 > div > div > div.list-tab > div:nth-child(2) > div > div > div > div > div.left > div:nth-child(2) > div.p-t-8 > div > div > input"  # TODO: confirm real selector
POPUP_ACCOUNT_EARN_OPTIONS_CONTAINER = "#app > div.modals-container > div > div.vfm__container.vfm--absolute.vfm--inset.vfm--outline-none.modal-container.null > div > div.modal__content.flex-column.flex1 > div > div > div.list-tab > div:nth-child(2) > div > div > div > div > div.left > div:nth-child(2) > div.p-t-8 > div > div.dropdown-container"  # TODO: confirm real selector


def account_option_selector(account_name: str, container: str = POPUP_ACCOUNT_SPEND_OPTIONS_CONTAINER) -> str:
    """Build a selector for the account option labeled `account_name`
    (e.g. "PayLah", "DBS") within the currently-open account dropdown.

    Scoped under `container` (defaults to the Spend tab's options
    container; pass POPUP_ACCOUNT_EARN_OPTIONS_CONTAINER for the Earn tab)
    so it only matches options within the open dropdown, not any other
    text elsewhere on the page.
    """
    return f'{container} >> text="{account_name}"'


POPUP_DATE_SPEND_INPUT = "#app > div.modals-container > div > div.vfm__container.vfm--absolute.vfm--inset.vfm--outline-none.modal-container.null > div > div.modal__content.flex-column.flex1 > div > div > div.list-tab > div > div > div > div > div:nth-child(1) > div.left > div:nth-child(3) > div > div input"

# Dummy placeholder guessed from the Spend tab's structure - unconfirmed.
POPUP_DATE_EARN_INPUT = "#app > div.modals-container > div > div.vfm__container.vfm--absolute.vfm--inset.vfm--outline-none.modal-container.null > div > div.modal__content.flex-column.flex1 > div > div > div.list-tab > div:nth-child(2) > div > div > div > div > div.left > div:nth-child(3) > div > div input"

# Category defaults to the placeholder text "Bars & Coffee" already shown by
# MISA, matching the fixed CATEGORY constant in mapper.py. Filled via
# tx.category (not hardcoded here) so a future per-row/DB-derived category
# can be supported by changing only mapper.py.
POPUP_CATEGORY_SPEND_INPUT = "#app > div.modals-container > div > div.vfm__container.vfm--absolute.vfm--inset.vfm--outline-none.modal-container.null > div > div.modal__content.flex-column.flex1 > div > div > div.list-tab > div > div > div > div > div:nth-child(1) > div.right > div:nth-child(1) > div.p-t-8.categories > div > div.input-container input"

# Dummy placeholder guessed from the Spend tab's structure - unconfirmed.
POPUP_CATEGORY_EARN_INPUT = "#app > div.modals-container > div > div.vfm__container.vfm--absolute.vfm--inset.vfm--outline-none.modal-container.null > div > div.modal__content.flex-column.flex1 > div > div > div.list-tab > div:nth-child(2) > div > div > div > div > div.right > div:nth-child(1) > div.p-t-8.categories > div > div input"
POPUP_SAVE_AND_ADD_BUTTON = "#app > div.modals-container > div > div.vfm__container.vfm--absolute.vfm--inset.vfm--outline-none.modal-container.null > div > div.modal__footer > div > div.footer-button > button.ms-button.btn.pos-relative.primary-outline.primary-outline"  # TODO: confirm real selector

# MISA's popup footer has TWO save buttons: "Lưu và thêm" (Save & Add
# Another, POPUP_SAVE_AND_ADD_BUTTON above) and the plain "Lưu" (Save &
# Close) - this one. Their CSS classes look nearly identical
# (primary-outline vs primary), so this is scoped to the same
# footer-button container and matched via an EXACT text locator
# (text="Lưu") to avoid accidentally matching "Lưu và thêm" too.
# CONFIRMED (2026-08-08) - clicking it closes the popup and the new row
# appears in the transaction list (unlike POPUP_SAVE_AND_ADD_BUTTON, which
# leaves the popup open in "add another" mode).
POPUP_SAVE_AND_CLOSE_BUTTON = '#app > div.modals-container > div > div.vfm__container.vfm--absolute.vfm--inset.vfm--outline-none.modal-container.null > div > div.modal__footer > div > div.footer-button >> text="Lưu"'

# Element(s) indicating the popup save succeeded (e.g. a success toast, or
# the popup closing and the new row appearing in the list).
SUCCESS_INDICATOR = "text=Saved successfully"  # TODO: confirm real selector

# Element(s) indicating the popup save failed (e.g. a validation error
# message within the popup).
ERROR_INDICATOR = ".popup-error-message"  # TODO: confirm real selector
