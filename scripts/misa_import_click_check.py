"""Manual, interactive check for `app.misa.client.click_import_button()`
against the real MISA Money Keeper site. Not part of the automated test
suite.

Usage:
    PYTHONPATH="$(pwd)" venv/bin/python scripts/misa_import_click_check.py

Reuses the saved storage_state session from misa_login_check.py if present
(and still valid); otherwise logs in fresh using MISA_USERNAME /
MISA_PASSWORD from .env.misa. Opens a *headed* (visible) browser so you can
watch the Import button click and confirm the Add Transaction popup opens.
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

from app.misa import client

load_dotenv(".env.misa")


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
            print("Login failed; cannot test the Import button")
            input("Press Enter to close the browser...")
            browser.close()
            return 1

        opened = client.click_import_button(page)
        print(f"Import popup {'opened' if opened else 'did NOT open'}")

        input("Press Enter to close the browser...")
        browser.close()

    return 0 if opened else 1


if __name__ == "__main__":
    sys.exit(main())
