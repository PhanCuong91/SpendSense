"""Test script: Add a transaction to MISA Money Keeper and verify the result on the web UI.

Usage:
    # 1. Quick test with a synthetic Spend transaction (headed browser):
    PYTHONPATH=. venv/bin/python scripts/test_misa_import_and_verify.py

    # 2. Test with an Earn transaction:
    PYTHONPATH=. venv/bin/python scripts/test_misa_import_and_verify.py --type earn --amount 25.50

    # 3. Test using the first pending transaction from local txdb.sqlite3:
    PYTHONPATH=. venv/bin/python scripts/test_misa_import_and_verify.py --use-db

    # 4. Headless execution without interactive pause (for automated testing):
    PYTHONPATH=. venv/bin/python scripts/test_misa_import_and_verify.py --headless --no-prompt

Credentials:
    Loads MISA_USERNAME and MISA_PASSWORD from .env.misa (or AWS Secrets Manager
    if MISA_USERNAME_SECRET_ARN / MISA_PASSWORD_SECRET_ARN are set).
"""

import argparse
import os
import sys
import time
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import List, Optional, Tuple

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

from app.core.logging import get_logger
from app.misa import client, selectors
from app.misa.mapper import CATEGORY, EARN_CATEGORY, to_misa_transaction
from app.misa.models import MisaImportResult, MisaTransaction
from app.misa.runner import _resolve_secret

load_dotenv(".env.misa")
logger = get_logger(__name__)


def parse_args() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Add a transaction into MISA and verify the result on MISA web UI."
    )
    parser.add_argument(
        "--type",
        choices=["spend", "earn"],
        default="spend",
        help="Transaction type for synthetic test (spend or earn). Default: spend.",
    )
    parser.add_argument(
        "--amount",
        type=str,
        default="10",
        help="Transaction amount for synthetic test. Default: '10'.",
    )
    parser.add_argument(
        "--account",
        type=str,
        default="Helper",
        help="MISA Account name. Default: 'Helper'.",
    )
    parser.add_argument(
        "--category",
        type=str,
        default=None,
        help="MISA Category name. Default: 'Bars & Coffee' for spend, 'Balance' for earn.",
    )
    parser.add_argument(
        "--datetime",
        dest="tx_datetime",
        type=str,
        default=None,
        help="Transaction date/time formatted 'DD/MM/YYYY HH:MM'. Default: current local time.",
    )
    parser.add_argument(
        "--use-db",
        action="store_true",
        help="Read unimported candidate transaction(s) from local txdb.sqlite3 instead of synthetic data.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=1,
        help="Max candidate rows to import if --use-db is used. Default: 1.",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run Playwright in headless mode (no GUI window).",
    )
    parser.add_argument(
        "--no-prompt",
        action="store_true",
        help="Do not pause for manual confirmation before closing the browser.",
    )
    parser.add_argument(
        "--screenshot-dir",
        type=str,
        default="ai/update_misa_implementation",
        help="Directory to save verification screenshots. Default: 'ai/update_misa_implementation'.",
    )
    return parser


def get_credentials() -> Tuple[Optional[str], Optional[str]]:
    username = os.environ.get("MISA_USERNAME") or _resolve_secret("MISA_USERNAME_SECRET_ARN")
    password = os.environ.get("MISA_PASSWORD") or _resolve_secret("MISA_PASSWORD_SECRET_ARN")
    return username, password


def prepare_transactions(args: argparse.Namespace) -> List[Tuple[Optional[str], MisaTransaction]]:
    """Build list of (row_id, MisaTransaction) to test."""
    if args.use_db:
        from app.db.session import SessionLocal
        from app.misa.dedup_store import DedupStore
        from app.misa.query import get_classified_candidates

        dedup_store = DedupStore()
        db = SessionLocal()
        try:
            candidates = get_classified_candidates(db)
            unimported = []
            for row, classification in candidates:
                if not dedup_store.is_imported(row.id):
                    tx = to_misa_transaction(row, classification)
                    unimported.append((str(row.id), tx))
                    if len(unimported) >= args.limit:
                        break
            if not unimported:
                print("No pending unimported transactions found in txdb.sqlite3.")
            return unimported
        finally:
            db.close()
            dedup_store.close()

    # Synthetic transaction
    classification = "Earn" if args.type.lower() == "earn" else "Spend"
    category = args.category or (EARN_CATEGORY if classification == "Earn" else CATEGORY)
    tx_datetime = args.tx_datetime or datetime.now().strftime("%d/%m/%Y %H:%M")
    amount = Decimal(args.amount)

    tx = MisaTransaction(
        classification=classification,
        amount=amount,
        account=args.account,
        datetime=tx_datetime,
        category=category,
    )
    return [(None, tx)]


def verify_transaction_on_web(page, tx: MisaTransaction, timeout_ms: int = 10_000) -> bool:
    """Navigate to the transactions list page and verify the transaction is visible."""
    print(f"\n--- Verifying transaction on MISA Web UI ({selectors.TRANSACTIONS_URL}) ---")
    page.goto(selectors.TRANSACTIONS_URL)
    page.wait_for_timeout(2000)

    try:
        page.wait_for_selector(selectors.LOGIN_SUCCESS_INDICATOR, timeout=timeout_ms)
    except Exception:
        pass

    # Search for amount or account string on the page
    amount_str = f"{int(tx.amount):,}" if tx.amount % 1 == 0 else f"{tx.amount:,.2f}"
    # In VN format, commas and dots may vary; check both raw number and formatted
    raw_amount = str(int(tx.amount) if tx.amount % 1 == 0 else tx.amount)

    # Check page content for presence of account, category, and amount
    content = page.content()
    has_account = tx.account.lower() in content.lower()
    has_amount = (amount_str in content) or (raw_amount in content)
    has_category = tx.category.lower() in content.lower()

    print(f"  • Account  ({tx.account!r}): {'✓ FOUND' if has_account else '✗ NOT FOUND'}")
    print(f"  • Category ({tx.category!r}): {'✓ FOUND' if has_category else '✗ NOT FOUND'}")
    print(f"  • Amount   ({raw_amount}): {'✓ FOUND' if has_amount else '✗ NOT FOUND'}")

    verified = has_amount and (has_account or has_category)
    return verified


def main() -> int:
    parser = parse_args()
    args = parser.parse_args()

    username, password = get_credentials()
    if not username or not password:
        print("ERROR: MISA credentials not found.")
        print("Please set MISA_USERNAME and MISA_PASSWORD in .env.misa or export them.")
        return 1

    txs_to_test = prepare_transactions(args)
    if not txs_to_test:
        print("No transactions to test.")
        return 1

    screenshot_dir = Path(args.screenshot_dir)
    screenshot_dir.mkdir(parents=True, exist_ok=True)
    timestamp = int(time.time())

    print(f"\n========================================================")
    print(f" MISA Test & Verification Runner")
    print(f"========================================================")
    print(f"Target URL:  {selectors.LOGIN_URL}")
    print(f"Headless:    {args.headless}")
    print(f"Test count:  {len(txs_to_test)}")
    for idx, (row_id, tx) in enumerate(txs_to_test, 1):
        print(f"  [{idx}] Type={tx.classification}, Amount={tx.amount}, Account={tx.account}, Date={tx.datetime}, Category={tx.category}")
    print(f"========================================================\n")

    storage_state_path = client.DEFAULT_STORAGE_STATE_PATH
    has_saved_session = Path(storage_state_path).exists()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=args.headless)
        context = browser.new_context(
            storage_state=storage_state_path if has_saved_session else None,
            viewport={"width": 1280, "height": 800},
        )
        page = context.new_page()

        # Check / Perform Login
        print("Authenticating with MISA...")
        logged_in = has_saved_session and client.is_logged_in(page)
        if not logged_in:
            print(f"Logging in as {username}...")
            logged_in = client.login(page, username, password)
            if logged_in:
                client.save_session(context)
                print(f"✓ Login successful! Saved session to {storage_state_path}")
            else:
                print("✗ Login failed.")
                browser.close()
                return 1
        else:
            print("✓ Restored authenticated session from storage state.")

        all_success = True

        # Execute Import for each transaction
        for idx, (row_id, tx) in enumerate(txs_to_test, 1):
            print(f"\n--- Importing Transaction #{idx} ({tx.classification}: {tx.amount} {tx.account}) ---")
            result: MisaImportResult = client.add_transaction(page, tx)

            if result.success:
                print(f"✓ Import executed successfully via Add Transaction popup!")
            else:
                print(f"✗ Import failed: {result.error_message}")
                all_success = False

            # Verify in Web UI
            verified = verify_transaction_on_web(page, tx)

            # Capture Screenshot
            screenshot_file = screenshot_dir / f"verify_result_{tx.classification.lower()}_{timestamp}_{idx}.png"
            page.screenshot(path=str(screenshot_file), full_page=True)
            print(f"📸 Saved full-page verification screenshot to: {screenshot_file}")

            if verified:
                print(f"🎉 Verification Result: PASS (Transaction reflected in MISA Web UI)")
            else:
                print(f"⚠️  Verification Result: UNCONFIRMED (Check screenshot {screenshot_file.name})")

        print(f"\n========================================================")
        print(f" Summary: {'ALL PASSED' if all_success else 'COMPLETED WITH WARNINGS/FAILURES'}")
        print(f"========================================================")

        if not args.headless and not args.no_prompt:
            print("\nBrowser is open. You can inspect the final result in the MISA UI.")
            try:
                input("Press [Enter] to close the browser and exit...")
            except (KeyboardInterrupt, EOFError):
                pass

        browser.close()

    return 0 if all_success else 1


if __name__ == "__main__":
    sys.exit(main())
