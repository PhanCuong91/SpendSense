"""Test MISA import runner end-to-end via Docker container and verify on MISA Web UI.

Flow:
1. (Optional) Seed a sample Spend/Earn candidate into local data/txdb.sqlite3.
2. Build or use the Docker image (spend_sense:test).
3. Run the container with APP_ROLE=misa against local SQLite DB and MISA credentials.
4. Inspect local txdb.sqlite3 to confirm misa_import_state was updated.
5. Open MISA Web UI to verify the transaction appears in the live web application.
6. Capture a screenshot as visual proof and print a summary.

Usage:
    # 1. Standard test (builds Docker image, seeds sample transaction, runs container, verifies web UI):
    PYTHONPATH=. venv/bin/python scripts/test_misa_docker.py

    # 2. Test with custom amount and account:
    PYTHONPATH=. venv/bin/python scripts/test_misa_docker.py --amount 15.00 --account "Helper" --type spend

    # 3. Skip Docker build (use existing spend_sense:test image):
    PYTHONPATH=. venv/bin/python scripts/test_misa_docker.py --no-build

    # 4. Headless verification (for automated CI):
    PYTHONPATH=. venv/bin/python scripts/test_misa_docker.py --headless --no-prompt
"""

import argparse
import os
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Optional, Tuple

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

from app.core.logging import get_logger
from app.misa import client, selectors
from app.misa.mapper import CATEGORY, EARN_CATEGORY
from app.misa.models import MisaTransaction

load_dotenv(".env.misa")
logger = get_logger(__name__)


def parse_args() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run MISA import inside Docker container and verify on MISA Web UI."
    )
    parser.add_argument(
        "--image",
        type=str,
        default="spend_sense:test",
        help="Docker image tag to test. Default: 'spend_sense:test'.",
    )
    parser.add_argument(
        "--no-build",
        action="store_true",
        help="Skip 'docker build' and use existing image.",
    )
    parser.add_argument(
        "--type",
        choices=["spend", "earn"],
        default="spend",
        help="Type of sample candidate transaction to insert if DB is empty. Default: spend.",
    )
    parser.add_argument(
        "--amount",
        type=str,
        default="10",
        help="Amount for sample candidate transaction. Default: '10'.",
    )
    parser.add_argument(
        "--account",
        type=str,
        default="Helper",
        help="Account for sample candidate transaction. Default: 'Helper'.",
    )
    parser.add_argument(
        "--category",
        type=str,
        default=None,
        help="Category name. Default: 'Bars & Coffee' for spend, 'Balance' for earn.",
    )
    parser.add_argument(
        "--db-path",
        type=str,
        default="data/txdb.sqlite3",
        help="Local SQLite DB path. Default: 'data/txdb.sqlite3'.",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run Playwright verification in headless mode.",
    )
    parser.add_argument(
        "--no-prompt",
        action="store_true",
        help="Do not pause for manual confirmation before closing verification browser.",
    )
    parser.add_argument(
        "--screenshot-dir",
        type=str,
        default="ai/update_misa_implementation",
        help="Directory to save verification screenshots.",
    )
    return parser


def ensure_database(db_path: Path):
    """Ensure SQLite DB file and tables exist via Alembic."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if not db_path.exists() or db_path.stat().st_size == 0:
        print(f"Initializing database schema in {db_path} via Alembic...")
        cmd = [
            "venv/bin/alembic",
            "upgrade",
            "head",
        ]
        env = os.environ.copy()
        env["PYTHONPATH"] = "."
        env["DATABASE_URL"] = f"sqlite:///{db_path}"
        subprocess.run(cmd, env=env, check=True)


def seed_sample_candidate_if_needed(
    db_path: Path, tx_type: str, amount_str: str, account_name: str
) -> Tuple[uuid.UUID, MisaTransaction]:
    """Seed a candidate transaction into parsed_transaction_candidate if no unimported ones exist."""
    from app.db.models.parsed_candidate import ParsedTransactionCandidate
    from app.db.session import SessionLocal
    from app.misa.dedup_store import DedupStore
    from app.misa.mapper import to_misa_transaction
    from app.misa.query import get_classified_candidates

    dedup_store = DedupStore()
    db = SessionLocal()
    try:
        candidates = get_classified_candidates(db)
        unimported = [c for c in candidates if not dedup_store.is_imported(c[0].id)]
        if unimported:
            row, classification = unimported[0]
            tx = to_misa_transaction(row, classification)
            print(f"Found existing pending unimported candidate in DB: ID={row.id}, Type={classification}, Amount={tx.amount}, Account={tx.account}")
            return row.id, tx

        # Seed new sample candidate
        candidate_id = uuid.uuid4()
        is_spend = tx_type.lower() == "spend"
        classification = "Spend" if is_spend else "Earn"
        category = EARN_CATEGORY if classification == "Earn" else CATEGORY
        amount = Decimal(amount_str)
        now = datetime.now(timezone.utc)
        datetime_str = now.strftime("%d/%m/%Y %H:%M")

        new_candidate = ParsedTransactionCandidate(
            id=candidate_id,
            email_id=f"test-email-{int(time.time())}",
            bank="DBS",
            account_display=account_name,
            amount=amount,
            currency="SGD",
            direction="debit" if is_spend else "credit",
            txn_time=now,
            recipient=None if is_spend else account_name,
            sender=account_name if is_spend else None,
            inferred_sender=account_name if is_spend else None,
            inferred_receiver=None if is_spend else account_name,
            is_spend=is_spend,
            is_internal_transfer=False,
            is_earning=not is_spend,
            created_at=now,
        )
        db.add(new_candidate)
        db.commit()

        tx = MisaTransaction(
            classification=classification,
            amount=amount,
            account=account_name,
            datetime=datetime_str,
            category=category,
        )
        print(f"Seeded new test candidate in {db_path}: ID={candidate_id}, Type={classification}, Amount={amount}, Account={account_name}")
        return candidate_id, tx
    finally:
        db.close()
        dedup_store.close()


def build_docker_image(image_tag: str):
    """Build the Docker image."""
    print(f"\nBuilding Docker image '{image_tag}'...")
    cmd = ["docker", "build", "-t", image_tag, "."]
    subprocess.run(cmd, check=True)
    print(f"✓ Docker image '{image_tag}' built successfully.\n")


def run_docker_misa(image_tag: str, db_path: Path, username: str, password: str) -> int:
    """Run the MISA runner container."""
    print(f"\nRunning MISA runner in Docker container ({image_tag})...")
    abs_data_dir = str(db_path.parent.resolve())
    abs_ai_dir = str(Path("ai").resolve())

    docker_cmd = [
        "docker",
        "run",
        "--rm",
        "-e",
        "APP_ROLE=misa",
        "-e",
        "DATABASE_URL=sqlite:///./data/txdb.sqlite3",
        "-e",
        f"MISA_USERNAME={username}",
        "-e",
        f"MISA_PASSWORD={password}",
        "-v",
        f"{abs_data_dir}:/app/data",
        "-v",
        f"{abs_ai_dir}:/app/ai",
        image_tag,
        "sh",
        "-c",
        "playwright install chromium && python -m app.misa.runner",
    ]

    result = subprocess.run(docker_cmd)
    return result.returncode


def verify_db_state(candidate_id: uuid.UUID) -> bool:
    """Verify that candidate_id was marked as imported in SQLite."""
    from app.misa.dedup_store import DedupStore

    dedup = DedupStore()
    try:
        imported = dedup.is_imported(candidate_id)
        return imported
    finally:
        dedup.close()


def verify_on_misa_web(tx: MisaTransaction, headless: bool, screenshot_path: Path) -> bool:
    """Open MISA Web UI and check that the transaction appears."""
    print(f"\n--- Verifying Result on MISA Web UI ({selectors.TRANSACTIONS_URL}) ---")
    storage_state_path = client.DEFAULT_STORAGE_STATE_PATH
    has_saved_session = Path(storage_state_path).exists()

    username = os.environ.get("MISA_USERNAME")
    password = os.environ.get("MISA_PASSWORD")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context(
            storage_state=storage_state_path if has_saved_session else None,
            viewport={"width": 1280, "height": 800},
        )
        page = context.new_page()

        logged_in = has_saved_session and client.is_logged_in(page)
        if not logged_in and username and password:
            print(f"Logging in as {username}...")
            logged_in = client.login(page, username, password)
            if logged_in:
                client.save_session(context)

        page.goto(selectors.TRANSACTIONS_URL)
        page.wait_for_timeout(3000)

        # Check page content for presence of account, category, and amount
        amount_str = f"{int(tx.amount):,}" if tx.amount % 1 == 0 else f"{tx.amount:,.2f}"
        raw_amount = str(int(tx.amount) if tx.amount % 1 == 0 else tx.amount)

        content = page.content()
        has_account = tx.account.lower() in content.lower()
        has_amount = (amount_str in content) or (raw_amount in content)
        has_category = tx.category.lower() in content.lower()

        print(f"  • Account  ({tx.account!r}): {'✓ FOUND' if has_account else '✗ NOT FOUND'}")
        print(f"  • Category ({tx.category!r}): {'✓ FOUND' if has_category else '✗ NOT FOUND'}")
        print(f"  • Amount   ({raw_amount}): {'✓ FOUND' if has_amount else '✗ NOT FOUND'}")

        page.screenshot(path=str(screenshot_path), full_page=True)
        print(f"📸 Full-page verification screenshot saved to: {screenshot_path}")

        verified = has_amount and (has_account or has_category)
        return verified


def main() -> int:
    parser = parse_args()
    args = parser.parse_args()

    username = os.environ.get("MISA_USERNAME")
    password = os.environ.get("MISA_PASSWORD")
    if not username or not password:
        print("ERROR: MISA_USERNAME and MISA_PASSWORD must be configured in .env.misa")
        return 1

    db_path = Path(args.db_path)
    ensure_database(db_path)

    # 1. Seed or find candidate
    candidate_id, tx = seed_sample_candidate_if_needed(
        db_path, args.type, args.amount, args.account
    )

    # 2. Build Docker image if needed
    if not args.no_build:
        build_docker_image(args.image)

    # 3. Run container
    exit_code = run_docker_misa(args.image, db_path, username, password)
    if exit_code != 0:
        print(f"✗ Docker container exited with non-zero status: {exit_code}")
        return exit_code
    print("✓ Docker container completed successfully!")

    # 4. Check SQLite DB state
    db_updated = verify_db_state(candidate_id)
    print(f"  • Database misa_import_state updated for candidate {candidate_id}: {'✓ YES' if db_updated else '✗ NO'}")

    # 5. Verify on MISA Web UI
    timestamp = int(time.time())
    screenshot_dir = Path(args.screenshot_dir)
    screenshot_dir.mkdir(parents=True, exist_ok=True)
    screenshot_path = screenshot_dir / f"docker_verify_{tx.classification.lower()}_{timestamp}.png"

    web_verified = verify_on_misa_web(tx, args.headless, screenshot_path)

    print(f"\n========================================================")
    print(f" Final Test Verdict")
    print(f"========================================================")
    print(f"Docker Execution:        {'PASS' if exit_code == 0 else 'FAIL'}")
    print(f"Database Dedup State:    {'PASS' if db_updated else 'FAIL'}")
    print(f"MISA Web UI Reflection:  {'PASS' if web_verified else 'UNCONFIRMED'}")
    print(f"Verification Screenshot: {screenshot_path}")
    print(f"========================================================\n")

    if not args.headless and not args.no_prompt:
        try:
            input("Press [Enter] to finish and exit...")
        except (KeyboardInterrupt, EOFError):
            pass

    return 0 if (exit_code == 0 and db_updated) else 1


if __name__ == "__main__":
    sys.exit(main())
