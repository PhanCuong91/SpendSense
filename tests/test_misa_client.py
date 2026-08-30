"""Playwright tests for app/misa/client.py, exercised against the static
HTML fixtures in tests/fixtures/ instead of the real MISA site.

Reuses the same login/click/fill/save flow already validated manually via
scripts/misa_login_check.py and scripts/misa_fill_popup_spend_check.py
(see ai/update_misa_implementation/update_misa_tasks.md §5.2 item 5) --
only pointed at tests/fixtures/misa_login.html and
tests/fixtures/misa_transactions.html (via selectors.LOGIN_URL /
selectors.TRANSACTIONS_URL monkeypatched to file:// URIs) instead of the
production URLs, so this suite never touches the real MISA account.
"""

from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright

from app.misa import client, selectors
from app.misa.models import MisaTransaction

FIXTURES_DIR = Path(__file__).parent / "fixtures"
LOGIN_FIXTURE_URL = (FIXTURES_DIR / "misa_login.html").resolve().as_uri()
TRANSACTIONS_FIXTURE_URL = (FIXTURES_DIR / "misa_transactions.html").resolve().as_uri()

# Must match tests/fixtures/misa_login.html's FIXTURE_VALID_USERNAME/PASSWORD.
FIXTURE_VALID_USERNAME = "fixture_user"
FIXTURE_VALID_PASSWORD = "fixture_pass"


@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as p:
        b = p.chromium.launch()
        yield b
        b.close()


@pytest.fixture()
def page(browser):
    context = browser.new_context()
    pg = context.new_page()
    # Speed up the "bad account" tests: Playwright's default 30s action
    # timeout would otherwise apply to every click() against a selector
    # that legitimately never matches (e.g. an unknown account option).
    pg.set_default_timeout(3_000)
    yield pg
    context.close()


@pytest.fixture(autouse=True)
def _fixture_urls(monkeypatch):
    """Point client.py's login()/is_logged_in() at the local fixtures
    instead of the real MISA URLs (selectors.py attributes are looked up
    at call time, so this affects client.py without editing it)."""
    monkeypatch.setattr(selectors, "LOGIN_URL", LOGIN_FIXTURE_URL)
    monkeypatch.setattr(selectors, "TRANSACTIONS_URL", TRANSACTIONS_FIXTURE_URL)


@pytest.fixture(autouse=True)
def _skip_account_settle_wait(monkeypatch):
    """The real popup waits ~2.5s for MISA's async default-account load to
    settle before touching the account field; the fixture has no such
    async behavior, so skip the wait to keep the suite fast."""
    monkeypatch.setattr(client, "POPUP_ACCOUNT_SETTLE_MS", 0)
    monkeypatch.setattr(client, "POPUP_CLOSE_SETTLE_MS", 0)


def _goto_transactions(page):
    page.goto(selectors.TRANSACTIONS_URL)


# --- login() success/failure detection -----------------------------------


def test_login_success(page):
    assert client.login(page, FIXTURE_VALID_USERNAME, FIXTURE_VALID_PASSWORD) is True


def test_login_failure_wrong_password(page):
    assert client.login(page, FIXTURE_VALID_USERNAME, "wrong-password") is False


def test_login_failure_unknown_username(page):
    assert client.login(page, "not-a-real-user", FIXTURE_VALID_PASSWORD) is False


# --- add_transaction() success/failure detection --------------------------


def test_add_transaction_success_spend(page):
    _goto_transactions(page)
    tx = MisaTransaction(
        amount=10,
        account="Helper",
        datetime="08/08/2026 10:00",
        category="Bars & Coffee",
        classification="Spend",
    )
    result = client.add_transaction(page, tx)
    assert result.success is True
    assert result.error_message is None


def test_add_transaction_success_earn(page):
    _goto_transactions(page)
    tx = MisaTransaction(
        amount=10,
        account="Helper",
        datetime="08/08/2026 10:00",
        category="Balance",
        classification="Earn",
    )
    result = client.add_transaction(page, tx)
    assert result.success is True
    assert result.error_message is None


def test_add_transaction_failure_bad_account(page):
    _goto_transactions(page)
    tx = MisaTransaction(
        amount=10,
        account="No Such Account",
        datetime="08/08/2026 10:00",
        category="Bars & Coffee",
        classification="Spend",
    )
    result = client.add_transaction(page, tx)
    assert result.success is False
    assert result.error_message is not None


def test_add_transaction_one_failure_does_not_stop_others(page):
    """A failed row (e.g. an account that can't be found) must not raise
    and must not prevent subsequent rows from being processed."""
    _goto_transactions(page)

    bad_tx = MisaTransaction(
        amount=10,
        account="No Such Account",
        datetime="08/08/2026 10:00",
        category="Bars & Coffee",
        classification="Spend",
    )
    bad_result = client.add_transaction(page, bad_tx)
    assert bad_result.success is False

    good_tx = MisaTransaction(
        amount=20,
        account="Cash",
        datetime="08/08/2026 10:00",
        category="Bars & Coffee",
        classification="Spend",
    )
    good_result = client.add_transaction(page, good_tx)
    assert good_result.success is True


def test_add_transaction_exception_is_caught_not_raised(page, monkeypatch):
    """Any unexpected exception inside add_transaction() (e.g. a selector
    that no longer matches) must be converted into a failed result, never
    propagate to the caller's loop."""
    monkeypatch.setattr(selectors, "IMPORT_BUTTON", "#this-selector-does-not-exist")
    _goto_transactions(page)

    tx = MisaTransaction(
        amount=10,
        account="Helper",
        datetime="08/08/2026 10:00",
        category="Bars & Coffee",
        classification="Spend",
    )
    result = client.add_transaction(page, tx)

    assert result.success is False
    assert result.error_message
