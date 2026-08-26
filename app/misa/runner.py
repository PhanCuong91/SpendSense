"""CLI entrypoint: import not-yet-imported Spend/Earn transactions from
`data/txdb.sqlite3` into MISA Money Keeper.

Usage:
    python -m app.misa.runner [--start-date YYYY-MM-DD] [--end-date YYYY-MM-DD]
        [--headed] [--dry-run] [--limit N]

See ai/update_misa_implementation/update_misa_design.md §5/§6/§7 for the
orchestration, logging, and CLI design this implements.

Orchestration: query + classify + map -> filter already-imported rows (using
`misa_import_state`) -> (--dry-run: print planned imports, exit) -> else
launch Playwright, log in, loop rows calling `client.add_transaction()`,
insert a `misa_import_state` row on each success, log per-row success/failure,
print an end-of-run summary.

Credentials: MISA_USERNAME / MISA_PASSWORD are loaded from `.env.misa` (kept
separate from the main `.env`, gitignored) via python-dotenv, matching the
convention already established by scripts/misa_login_check.py and friends.
"""

import argparse
import os
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import List, Optional, Tuple

from dotenv import load_dotenv

from app.core.logging import get_logger

# Expose sync_playwright at module level so tests can monkeypatch it without
# forcing Playwright to be installed at import time. The real import happens
# inside _run_import() only when a browser is actually needed.
sync_playwright = None
from app.db.models.parsed_candidate import ParsedTransactionCandidate
from app.db.session import SessionLocal
from app.misa import client
from app.misa.dedup_store import DedupStore
from app.misa.mapper import to_misa_transaction
from app.misa.models import MisaTransaction
from app.misa.query import Classification, get_classified_candidates

logger = get_logger(__name__)

PlannedRow = Tuple[ParsedTransactionCandidate, Classification, MisaTransaction]


def _parse_date(value: str) -> date:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"Invalid date {value!r}, expected YYYY-MM-DD") from exc


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Import not-yet-imported Spend/Earn transactions into MISA Money Keeper."
    )
    parser.add_argument("--start-date", type=_parse_date, default=None, help="Inclusive start date (YYYY-MM-DD)")
    parser.add_argument("--end-date", type=_parse_date, default=None, help="Inclusive end date (YYYY-MM-DD)")
    parser.add_argument("--headed", action="store_true", help="Run with a visible (non-headless) browser")
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Import at most this many rows (useful for small manual verification runs)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Classify/map rows and print what would be imported, without launching a browser "
        "or touching the dedup store",
    )
    return parser


def _plan_rows(
    dedup_store: DedupStore, start_date: Optional[date], end_date: Optional[date]
) -> Tuple[List[PlannedRow], int, int]:
    """Query, classify, map, and filter out already-imported rows.

    Returns (planned_rows, considered_count, skipped_count).
    """
    db = SessionLocal()
    try:
        classified = get_classified_candidates(db, start_date=start_date, end_date=end_date)
        considered = len(classified)
        planned: List[PlannedRow] = []
        skipped = 0
        for row, classification in classified:
            if dedup_store.is_imported(row.id):
                skipped += 1
                continue
            planned.append((row, classification, to_misa_transaction(row, classification)))
        return planned, considered, skipped
    finally:
        db.close()


def _run_dry(planned: List[PlannedRow], considered: int, skipped: int) -> int:
    logger.info(
        "Dry run: %d row(s) would be imported (considered=%d, skipped(already imported)=%d)",
        len(planned),
        considered,
        skipped,
    )
    for row, classification, tx in planned:
        logger.info(
            "[would-import] id=%s type=%s amount=%s account=%s datetime=%s category=%s",
            row.id,
            classification,
            tx.amount,
            tx.account,
            tx.datetime,
            tx.category,
        )
    return 0


def _resolve_secret(arn_env_var: str) -> Optional[str]:
    """Resolve a value from AWS Secrets Manager when its ARN is provided.

    Falls back to None so plain environment variables remain the default for
    local development.
    """
    arn = os.environ.get(arn_env_var)
    if not arn:
        return None
    import boto3

    return boto3.client("secretsmanager").get_secret_value(SecretId=arn)["SecretString"]


def _run_import(planned: List[PlannedRow], considered: int, skipped: int, dedup_store: DedupStore, headed: bool) -> int:
    username = os.environ.get("MISA_USERNAME") or _resolve_secret("MISA_USERNAME_SECRET_ARN")
    password = os.environ.get("MISA_PASSWORD") or _resolve_secret("MISA_PASSWORD_SECRET_ARN")
    if not username or not password:
        logger.error(
            "MISA_USERNAME and MISA_PASSWORD must be set (see .env.misa), "
            "or their ARNs must be provided via MISA_USERNAME_SECRET_ARN / "
            "MISA_PASSWORD_SECRET_ARN"
        )
        return 1

    # Import Playwright only when actually launching a browser. This keeps the
    # Docker image free of the heavy playwright/Chromium dependency.
    from playwright.sync_api import sync_playwright as _sync_playwright

    imported = 0
    failed = 0

    with _sync_playwright() as p:
        browser = p.chromium.launch(headless=not headed)
        try:
            storage_state_path = client.DEFAULT_STORAGE_STATE_PATH
            has_saved_session = Path(storage_state_path).exists()
            context = browser.new_context(
                storage_state=storage_state_path if has_saved_session else None
            )
            page = context.new_page()

            logged_in = has_saved_session and client.is_logged_in(page)
            if not logged_in:
                logged_in = client.login(page, username, password)
                if logged_in:
                    client.save_session(context)

            if not logged_in:
                logger.error("Login failed; aborting run without attempting any imports")
                return 1

            for row, classification, tx in planned:
                result = client.add_transaction(page, tx)
                if result.success:
                    imported += 1
                    dedup_store.mark_imported(
                        row.id,
                        {
                            "imported_at": datetime.now(timezone.utc).isoformat(),
                            "amount": tx.amount,
                            "account": tx.account,
                            "datetime": tx.datetime,
                            "classification": classification,
                        },
                    )
                    logger.info(
                        "[imported] id=%s amount=%s account=%s datetime=%s",
                        row.id,
                        tx.amount,
                        tx.account,
                        tx.datetime,
                    )
                else:
                    failed += 1
                    logger.error(
                        "[failed]   id=%s amount=%s account=%s datetime=%s reason=%s",
                        row.id,
                        tx.amount,
                        tx.account,
                        tx.datetime,
                        result.error_message,
                    )
        finally:
            browser.close()

    logger.info(
        "Summary: considered=%d imported=%d failed=%d skipped(already imported)=%d",
        considered,
        imported,
        failed,
        skipped,
    )
    return 0 if failed == 0 else 1


def run(args: argparse.Namespace) -> int:
    dedup_store = DedupStore()
    try:
        planned, considered, skipped = _plan_rows(dedup_store, args.start_date, args.end_date)

        if args.limit is not None and args.limit >= 0:
            planned = planned[: args.limit]

        if args.dry_run:
            return _run_dry(planned, considered, skipped)

        if not planned:
            logger.info(
                "Summary: considered=%d imported=0 failed=0 skipped(already imported)=%d",
                considered,
                skipped,
            )
            return 0

        return _run_import(planned, considered, skipped, dedup_store, args.headed)
    finally:
        dedup_store.close()


def main(argv: Optional[List[str]] = None) -> int:
    load_dotenv(".env.misa")
    args = build_arg_parser().parse_args(argv)
    return run(args)


if __name__ == "__main__":
    sys.exit(main())
