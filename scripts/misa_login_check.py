"""Manual, interactive check for `app.misa.client.login()` against the real
MISA Money Keeper site. Not part of the automated test suite.

Usage:
    python scripts/misa_login_check.py [--bad-password]

--bad-password intentionally corrupts the real password so the failure /
LOGIN_ERROR_INDICATOR path can be exercised without editing .env.misa.

Reads MISA_USERNAME / MISA_PASSWORD from a local .env.misa file (via
python-dotenv, kept separate from the main .env and gitignored) and opens a
*headed* (visible) browser so you can watch the login flow and manually
complete any 2FA/captcha step if one appears. On success, the session is
saved to storage_state so subsequent runs can try to reuse it via
`client.is_logged_in()`.
"""

import os
import sys

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

from app.misa import client

load_dotenv(".env.misa")


def main() -> int:
    username = os.environ.get("MISA_USERNAME")
    password = os.environ.get("MISA_PASSWORD")
    if not username or not password:
        print("MISA_USERNAME and MISA_PASSWORD must be set in .env.misa")
        return 1

    if "--bad-password" in sys.argv[1:]:
        password = password + "-wrong"
        print("Using intentionally incorrect password to test the failure path")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()

        success = client.login(page, username, password)
        print(f"Login {'succeeded' if success else 'failed'}")

        if success:
            client.save_session(context)
            print(f"Session saved to {client.DEFAULT_STORAGE_STATE_PATH}")

        input("Press Enter to close the browser...")
        browser.close()

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
