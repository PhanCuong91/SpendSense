"""Manual, interactive check for filling the MISA Add Transaction popup with
an Earn-type transaction and clicking Save. Same field values as the Spend
check (amount=10, account=Helper, date=today, category=CATEGORY), but for
the Earn tab, and this one DOES click Save — it will create a real
transaction in the live MISA account. Not part of the automated test suite.

Usage:
    PYTHONPATH="$(pwd)" venv/bin/python scripts/misa_fill_popup_earn_check.py

Reuses the saved storage_state session if present (from
misa_login_check.py); otherwise logs in fresh using MISA_USERNAME /
MISA_PASSWORD from .env.misa.
"""

import os
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

from app.misa import client, selectors
from app.misa.mapper import EARN_CATEGORY

load_dotenv(".env.misa")

TEST_AMOUNT = "10"
TEST_ACCOUNT = "Helper"


def main() -> int:
    storage_state_path = client.DEFAULT_STORAGE_STATE_PATH
    has_saved_session = Path(storage_state_path).exists()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(
            storage_state=storage_state_path if has_saved_session else None
        )
        page = context.new_page()

        logged_in = has_saved_session and client.is_logged_in(page)
        if not logged_in:
            username = os.environ.get("MISA_USERNAME")
            password = os.environ.get("MISA_PASSWORD")
            if not username or not password:
                print("MISA_USERNAME and MISA_PASSWORD must be set in .env.misa")
                browser.close()
                return 1
            logged_in = client.login(page, username, password)
            if logged_in:
                client.save_session(context)

        if not logged_in:
            print("Login failed; cannot test the popup form")
            input("Press Enter to close the browser...")
            browser.close()
            return 1

        if not client.click_import_button(page):
            print("Import popup did not open")
            input("Press Enter to close the browser...")
            browser.close()
            return 1
        print("Import popup opened")

        try:
            page.click(selectors.POPUP_EARN_TAB)
            print("Clicked Earn tab")
        except Exception as exc:
            print(f"Clicking Earn tab FAILED: {exc}")

        # Switching tabs re-triggers MISA's async default-account load for
        # the Earn panel, same as the initial popup open (see
        # client.POPUP_ACCOUNT_SETTLE_MS) - wait for it to settle before
        # touching the account field, otherwise the selection gets
        # silently reverted a couple seconds later.
        page.wait_for_timeout(client.POPUP_ACCOUNT_SETTLE_MS)

        try:
            page.fill(selectors.POPUP_AMOUNT_EARN_INPUT, TEST_AMOUNT)
            print(f"Filled amount = {TEST_AMOUNT}")
        except Exception as exc:
            print(f"Filling amount FAILED: {exc}")

        try:
            page.click(selectors.POPUP_ACCOUNT_EARN_INPUT)
            page.wait_for_selector(selectors.POPUP_ACCOUNT_EARN_OPTIONS_CONTAINER, timeout=client.POPUP_TIMEOUT_MS)
            page.click(selectors.account_option_selector(TEST_ACCOUNT, container=selectors.POPUP_ACCOUNT_EARN_OPTIONS_CONTAINER))
            print(f"Selected account = {TEST_ACCOUNT!r}")
        except Exception as exc:
            print(f"Selecting account {TEST_ACCOUNT!r} FAILED: {exc}")

        today_str = datetime.now().strftime("%d/%m/%Y %H:%M")
        try:
            page.fill(selectors.POPUP_DATE_EARN_INPUT, today_str)
            print(f"Filled date = {today_str}")
        except Exception as exc:
            print(f"Filling date FAILED: {exc}")

        try:
            page.fill(selectors.POPUP_CATEGORY_EARN_INPUT, EARN_CATEGORY)
            print(f"Filled category = {EARN_CATEGORY!r}")
        except Exception as exc:
            print(f"Filling category FAILED: {exc}")

        # Typing text alone only filters the dropdown - like the account
        # field, the matching option must be clicked to actually commit the
        # selection, otherwise Save's validation rejects it (red border,
        # popup stays open).
        try:
            page.click(f'{selectors.IMPORT_BUTTON_RESULT} >> text="{EARN_CATEGORY}"')
            print(f"Selected category option = {EARN_CATEGORY!r}")
        except Exception as exc:
            print(f"Selecting category option FAILED: {exc}")

        screenshot_path = f"ai/update_misa_implementation/popup_earn_debug_{int(datetime.now().timestamp())}.png"
        page.screenshot(path=screenshot_path)
        print(f"Saved pre-save screenshot to {screenshot_path}")

        try:
            page.click(selectors.POPUP_SAVE_AND_ADD_BUTTON)
            print("Clicked Save button")
        except Exception as exc:
            print(f"Clicking Save button FAILED: {exc}")
            input("Press Enter to close the browser...")
            browser.close()
            return 1

        try:
            page.wait_for_selector(
                f"{selectors.SUCCESS_INDICATOR}, {selectors.ERROR_INDICATOR}",
                timeout=client.POPUP_TIMEOUT_MS,
            )
            if page.locator(selectors.ERROR_INDICATOR).is_visible():
                print(f"Save FAILED: {page.locator(selectors.ERROR_INDICATOR).inner_text()}")
            elif page.locator(selectors.SUCCESS_INDICATOR).is_visible():
                print("Save SUCCEEDED")
            else:
                print("Neither success nor error indicator matched after wait")
        except Exception as exc:
            print(f"Waiting for success/error indicator FAILED: {exc}")

        result_screenshot_path = (
            f"ai/update_misa_implementation/popup_earn_result_{int(datetime.now().timestamp())}.png"
        )
        page.screenshot(path=result_screenshot_path)
        print(f"Saved post-save screenshot to {result_screenshot_path}")

        input("Inspect the result, then press Enter to close the browser...")
        browser.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
