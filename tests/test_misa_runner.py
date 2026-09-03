"""Tests for app/misa/runner.py's logging (§5.3 item 2) and .env /
.gitignore credential handling (§5.3 item 3).

These exercise `_run_dry`, `_run_import`, and `main()` directly with
fakes/mocks for Playwright, `client`, and the dedup store so they run fully
offline: no real browser, no real MISA credentials, no real DB.
"""
import logging
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db.models.email_raw import EmailRaw
from app.db.models.parsed_candidate import ParsedTransactionCandidate
from app.misa import runner
from app.misa.dedup_store import DedupStore
from app.misa.models import MisaImportResult, MisaTransaction


class _ListHandler(logging.Handler):
    """Captures records emitted by `runner.logger` directly.

    `app.core.logging.get_logger()` sets `propagate = False`, so pytest's
    `caplog` fixture (which attaches to the root logger) would silently miss
    every record. Attaching a handler straight to `runner.logger` sidesteps
    that.
    """

    def __init__(self):
        super().__init__()
        self.records = []

    def emit(self, record):
        self.records.append(record)


@pytest.fixture
def log_records():
    handler = _ListHandler()
    handler.setLevel(logging.INFO)
    runner.logger.addHandler(handler)
    previous_level = runner.logger.level
    runner.logger.setLevel(logging.INFO)
    try:
        yield handler.records
    finally:
        runner.logger.removeHandler(handler)
        runner.logger.setLevel(previous_level)


def _messages(records, level=None):
    return [r.getMessage() for r in records if level is None or r.levelno == level]


@pytest.fixture
def db_session():
    """Provide a function-scoped in-memory DB session for runner tests."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


def _make_candidate(session, amount, inferred_sender="Trust", inferred_receiver="Other"):
    email = EmailRaw(
        gmail_message_id=f"test-{uuid4()}",
        internal_date=datetime.now(timezone.utc),
    )
    session.add(email)
    session.commit()

    candidate = ParsedTransactionCandidate(
        email_id=email.id,
        amount=Decimal(str(amount)),
        currency="SGD",
        datetime_sgt=datetime(2026, 8, 8, 0, 0, tzinfo=timezone.utc),
        inferred_sender=inferred_sender,
        inferred_receiver=inferred_receiver,
    )
    session.add(candidate)
    session.commit()
    return candidate


def _planned_row(session, amount, account="Trust", classification="Spend"):
    row = _make_candidate(
        session,
        amount,
        inferred_sender=account if classification == "Spend" else "Other",
        inferred_receiver="Other" if classification == "Spend" else account,
    )
    tx = MisaTransaction(
        amount=amount,
        account=account,
        datetime="08/08/2026 00:00",
        category="Bars & Coffee" if classification == "Spend" else "Balance",
        classification=classification,
    )
    return row, classification, tx


class _FakePage:
    pass


class _FakeContext:
    def new_page(self):
        return _FakePage()


class _FakeBrowser:
    def __init__(self):
        self.closed = False

    def new_context(self, storage_state=None):
        return _FakeContext()

    def close(self):
        self.closed = True


class _FakeChromium:
    def __init__(self, browser):
        self._browser = browser

    def launch(self, headless=True):
        return self._browser


class _FakePlaywrightCM:
    def __init__(self, browser):
        self.chromium = _FakeChromium(browser)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def _fake_sync_playwright_factory():
    browser = _FakeBrowser()

    def _factory():
        return _FakePlaywrightCM(browser)

    return _factory


# ---------------------------------------------------------------------------
# Item 2: logging wired per the design's exact log line formats
# ---------------------------------------------------------------------------


def test_dry_run_logs_planned_rows(log_records, db_session):
    row, classification, tx = _planned_row(db_session, 1.23)

    exit_code = runner._run_dry([(row, classification, tx)], considered=1, skipped=0)

    assert exit_code == 0
    messages = _messages(log_records)
    assert any(m.startswith("Dry run: 1 row(s) would be imported") for m in messages)
    assert (
        f"[would-import] id={row.id} type=Spend amount=1.23 account=Trust datetime=08/08/2026 00:00 "
        "category=Bars & Coffee" in messages
    )


def test_imported_and_failed_log_lines_match_design_format(monkeypatch, db_session, log_records):
    ok_row, ok_classification, ok_tx = _planned_row(db_session, 1.23, account="Trust")
    bad_row, bad_classification, bad_tx = _planned_row(db_session, 4.56, account="PayLah")
    planned = [(ok_row, ok_classification, ok_tx), (bad_row, bad_classification, bad_tx)]

    monkeypatch.setenv("MISA_USERNAME", "u")
    monkeypatch.setenv("MISA_PASSWORD", "p")
    monkeypatch.setattr(runner.client, "is_logged_in", lambda page: True)
    monkeypatch.setattr(runner.client, "login", lambda page, username, password: True)
    monkeypatch.setattr(runner.client, "save_session", lambda ctx, path=None: None)

    def fake_add_transaction(page, tx):
        if tx is ok_tx:
            return MisaImportResult(success=True)
        return MisaImportResult(success=False, error_message="save button not found")

    monkeypatch.setattr(runner.client, "add_transaction", fake_add_transaction)
    monkeypatch.setattr(runner, "sync_playwright", _fake_sync_playwright_factory())

    dedup_store = DedupStore(db=db_session)
    exit_code = runner._run_import(planned, considered=2, skipped=0, dedup_store=dedup_store, headed=False)

    assert exit_code == 1  # at least one row failed
    info_messages = _messages(log_records, logging.INFO)
    error_messages = _messages(log_records, logging.ERROR)

    assert f"[imported] id={ok_row.id} amount=1.23 account=Trust datetime=08/08/2026 00:00" in info_messages
    assert (
        f"[failed]   id={bad_row.id} amount=4.56 account=PayLah datetime=08/08/2026 00:00 "
        "reason=save button not found" in error_messages
    )
    assert "Summary: considered=2 imported=1 failed=1 skipped(already imported)=0" in info_messages

    assert dedup_store.is_imported(ok_row.id) is True
    assert dedup_store.is_imported(bad_row.id) is False


def test_summary_logged_when_credentials_missing(monkeypatch, db_session, log_records):
    row, classification, tx = _planned_row(db_session, 1.0)

    monkeypatch.delenv("MISA_USERNAME", raising=False)
    monkeypatch.delenv("MISA_PASSWORD", raising=False)

    def _fail_if_called():
        raise AssertionError("sync_playwright() must not be called when credentials are missing")

    monkeypatch.setattr(runner, "sync_playwright", _fail_if_called)

    dedup_store = DedupStore(db=db_session)
    exit_code = runner._run_import([(row, classification, tx)], considered=1, skipped=0, dedup_store=dedup_store, headed=False)

    assert exit_code == 1
    error_messages = _messages(log_records, logging.ERROR)
    assert any("MISA_USERNAME and MISA_PASSWORD must be set" in m for m in error_messages)


# ---------------------------------------------------------------------------
# Item 3: .env support for MISA_USERNAME/MISA_PASSWORD + secrets never logged
# ---------------------------------------------------------------------------


def test_dry_run_limit_caps_planned_rows(log_records, monkeypatch, db_session):
    """--limit should cap the number of rows shown/considered for import."""
    row1, _, tx1 = _planned_row(db_session, 1.0)
    row2, _, tx2 = _planned_row(db_session, 2.0)
    row3, _, tx3 = _planned_row(db_session, 3.0)
    planned = [(row1, "Spend", tx1), (row2, "Spend", tx2), (row3, "Spend", tx3)]

    monkeypatch.setattr(runner, "_plan_rows", lambda *args, **kwargs: (planned, 3, 0))

    args = runner.build_arg_parser().parse_args(["--dry-run", "--limit", "2"])
    exit_code = runner.run(args)

    assert exit_code == 0
    messages = _messages(log_records)
    assert any("Dry run: 2 row(s) would be imported" in m for m in messages)
    assert sum(1 for m in messages if "[would-import]" in m) == 2


def test_main_loads_dotenv_from_env_misa_file_not_main_env(monkeypatch):
    calls = []
    monkeypatch.setattr(runner, "load_dotenv", lambda path=None: calls.append(path))
    monkeypatch.setattr(runner, "run", lambda args: 0)

    exit_code = runner.main(["--dry-run"])

    assert exit_code == 0
    assert calls == [".env.misa"]


def test_credentials_are_never_logged(monkeypatch, db_session, log_records):
    row, classification, tx = _planned_row(db_session, 1.0)

    monkeypatch.setenv("MISA_USERNAME", "secret_user_xyz")
    monkeypatch.setenv("MISA_PASSWORD", "supersecretpassword123")
    monkeypatch.setattr(runner.client, "is_logged_in", lambda page: True)
    monkeypatch.setattr(runner.client, "login", lambda page, username, password: True)
    monkeypatch.setattr(runner.client, "save_session", lambda ctx, path=None: None)
    monkeypatch.setattr(runner.client, "add_transaction", lambda page, tx: MisaImportResult(success=True))
    monkeypatch.setattr(runner, "sync_playwright", _fake_sync_playwright_factory())

    dedup_store = DedupStore(db=db_session)
    runner._run_import([(row, classification, tx)], considered=1, skipped=0, dedup_store=dedup_store, headed=False)

    all_messages = " ".join(_messages(log_records))
    assert "secret_user_xyz" not in all_messages
    assert "supersecretpassword123" not in all_messages


def test_resolve_ssm_param_when_env_vars_missing(monkeypatch, db_session):
    row, classification, tx = _planned_row(db_session, 1.0)

    monkeypatch.delenv("MISA_USERNAME", raising=False)
    monkeypatch.delenv("MISA_PASSWORD", raising=False)
    monkeypatch.setenv("MISA_USERNAME_PARAM_NAME", "/spendsense/misa_username")
    monkeypatch.setenv("MISA_PASSWORD_PARAM_NAME", "/spendsense/misa_password")

    resolved_params = {}

    def _fake_resolve_ssm(param_env_var: str):
        val = {"MISA_USERNAME_PARAM_NAME": "ssm_user", "MISA_PASSWORD_PARAM_NAME": "ssm_pass"}.get(param_env_var)
        resolved_params[param_env_var] = val
        return val

    monkeypatch.setattr(runner, "_resolve_ssm_param", _fake_resolve_ssm)
    monkeypatch.setattr(runner.client, "is_logged_in", lambda page: True)
    monkeypatch.setattr(runner.client, "login", lambda page, username, password: True)
    monkeypatch.setattr(runner.client, "save_session", lambda ctx, path=None: None)
    monkeypatch.setattr(runner.client, "add_transaction", lambda page, tx: MisaImportResult(success=True))
    monkeypatch.setattr(runner, "sync_playwright", _fake_sync_playwright_factory())

    dedup_store = DedupStore(db=db_session)
    exit_code = runner._run_import([(row, classification, tx)], considered=1, skipped=0, dedup_store=dedup_store, headed=False)

    assert exit_code == 0
    assert resolved_params["MISA_USERNAME_PARAM_NAME"] == "ssm_user"
    assert resolved_params["MISA_PASSWORD_PARAM_NAME"] == "ssm_pass"


def test_gitignore_covers_misa_secrets_and_session_state():
    repo_root = Path(runner.__file__).resolve().parents[2]
    content = (repo_root / ".gitignore").read_text()

    assert ".env.misa" in content
    assert "storage_state.json" in content
    assert "app.log" in content


# ---------------------------------------------------------------------------
# §5.3 items 4–5: Error recovery — reload / re-login (requirements §3.5)
# ---------------------------------------------------------------------------


class _FakePageWithReload:
    """Fake Page that records reload() calls and controls wait_for_selector."""

    def __init__(self, *, selector_ok: bool = True):
        self.reloaded = False
        self._selector_ok = selector_ok

    def reload(self, wait_until=None):
        self.reloaded = True

    def wait_for_selector(self, selector, timeout=None):
        if not self._selector_ok:
            raise Exception("selector not found")


def test_recovery_reload_ok_continues_to_next_row(monkeypatch, db_session, log_records):
    """After a failed row, page.reload() succeeds → [recovery] action=reload result=ok logged,
    run continues and remaining rows are imported."""
    ok_row, ok_cls, ok_tx = _planned_row(db_session, 1.0, account="Trust")
    bad_row, bad_cls, bad_tx = _planned_row(db_session, 2.0, account="PayLah")
    # bad_row comes first so the recovery path is exercised before ok_row
    planned = [(bad_row, bad_cls, bad_tx), (ok_row, ok_cls, ok_tx)]

    monkeypatch.setenv("MISA_USERNAME", "u")
    monkeypatch.setenv("MISA_PASSWORD", "p")
    monkeypatch.setattr(runner.client, "is_logged_in", lambda page: True)
    monkeypatch.setattr(runner.client, "login", lambda page, u, p: True)
    monkeypatch.setattr(runner.client, "save_session", lambda ctx, path=None: None)

    fake_page = _FakePageWithReload(selector_ok=True)  # reload lands on transactions page

    def fake_add(page, tx):
        if tx is bad_tx:
            return MisaImportResult(success=False, error_message="timeout")
        return MisaImportResult(success=True)

    monkeypatch.setattr(runner.client, "add_transaction", fake_add)
    monkeypatch.setattr(runner, "_recover_session",
        lambda page, ctx, row_id, username, password: (
            runner.logger.info("[recovery] row=%s action=reload result=ok", row_id) or True
        )
    )
    monkeypatch.setattr(runner, "sync_playwright", _fake_sync_playwright_factory())

    dedup_store = DedupStore(db=db_session)
    exit_code = runner._run_import(planned, considered=2, skipped=0, dedup_store=dedup_store, headed=False)

    assert exit_code == 1  # one failure → non-zero
    info_msgs = _messages(log_records, logging.INFO)
    assert any("[recovery]" in m and "action=reload result=ok" in m for m in info_msgs)
    # ok_row must still be imported despite the earlier failure
    assert dedup_store.is_imported(ok_row.id) is True
    assert dedup_store.is_imported(bad_row.id) is False


def test_recovery_relogin_ok_continues_to_next_row(monkeypatch, db_session, log_records):
    """After a failed row, reload lands on login page → re-login succeeds →
    [recovery] action=relogin result=ok logged, run continues."""
    bad_row, bad_cls, bad_tx = _planned_row(db_session, 3.0, account="ACB")
    ok_row, ok_cls, ok_tx = _planned_row(db_session, 4.0, account="Trust")
    planned = [(bad_row, bad_cls, bad_tx), (ok_row, ok_cls, ok_tx)]

    monkeypatch.setenv("MISA_USERNAME", "u")
    monkeypatch.setenv("MISA_PASSWORD", "p")
    monkeypatch.setattr(runner.client, "is_logged_in", lambda page: True)
    monkeypatch.setattr(runner.client, "login", lambda page, u, p: True)
    monkeypatch.setattr(runner.client, "save_session", lambda ctx, path=None: None)

    def fake_add(page, tx):
        if tx is bad_tx:
            return MisaImportResult(success=False, error_message="popup broke")
        return MisaImportResult(success=True)

    monkeypatch.setattr(runner.client, "add_transaction", fake_add)
    # Simulate: reload → selector fails (session expired) → relogin succeeds
    monkeypatch.setattr(runner, "_recover_session",
        lambda page, ctx, row_id, username, password: (
            runner.logger.info("[recovery] row=%s action=relogin result=ok", row_id) or True
        )
    )
    monkeypatch.setattr(runner, "sync_playwright", _fake_sync_playwright_factory())

    dedup_store = DedupStore(db=db_session)
    exit_code = runner._run_import(planned, considered=2, skipped=0, dedup_store=dedup_store, headed=False)

    assert exit_code == 1  # one failure
    info_msgs = _messages(log_records, logging.INFO)
    assert any("[recovery]" in m and "action=relogin result=ok" in m for m in info_msgs)
    assert dedup_store.is_imported(ok_row.id) is True


def test_recovery_relogin_failed_aborts_run(monkeypatch, db_session, log_records):
    """After a failed row, re-login also fails → run aborts immediately with
    exit code 1 and 'Re-login failed after error recovery' error logged.
    Remaining rows are NOT imported."""
    bad_row, bad_cls, bad_tx = _planned_row(db_session, 5.0, account="ACB")
    next_row, next_cls, next_tx = _planned_row(db_session, 6.0, account="Trust")
    planned = [(bad_row, bad_cls, bad_tx), (next_row, next_cls, next_tx)]

    monkeypatch.setenv("MISA_USERNAME", "u")
    monkeypatch.setenv("MISA_PASSWORD", "p")
    monkeypatch.setattr(runner.client, "is_logged_in", lambda page: True)
    monkeypatch.setattr(runner.client, "login", lambda page, u, p: True)
    monkeypatch.setattr(runner.client, "save_session", lambda ctx, path=None: None)

    def fake_add(page, tx):
        if tx is bad_tx:
            return MisaImportResult(success=False, error_message="crash")
        return MisaImportResult(success=True)

    monkeypatch.setattr(runner.client, "add_transaction", fake_add)
    # Simulate: reload fails AND re-login fails
    monkeypatch.setattr(runner, "_recover_session", lambda *args, **kwargs: False)
    monkeypatch.setattr(runner, "sync_playwright", _fake_sync_playwright_factory())

    dedup_store = DedupStore(db=db_session)
    exit_code = runner._run_import(planned, considered=2, skipped=0, dedup_store=dedup_store, headed=False)

    assert exit_code == 1
    error_msgs = _messages(log_records, logging.ERROR)
    assert any("Re-login failed after error recovery" in m for m in error_msgs)
    # next_row must NOT have been attempted
    assert dedup_store.is_imported(next_row.id) is False


def test_recovery_log_line_emitted_on_reload_ok(monkeypatch, db_session, log_records):
    """Unit-test _recover_session() directly: when reload succeeds (selector found),
    a [recovery] action=reload result=ok INFO line is emitted and True is returned."""
    from app.misa.runner import _recover_session

    fake_page = _FakePageWithReload(selector_ok=True)
    fake_context = _FakeContext()

    # login/save_session must not be called when reload succeeds
    monkeypatch.setattr(runner.client, "login", lambda *a, **kw: (_ for _ in ()).throw(AssertionError("login called")))
    monkeypatch.setattr(runner.client, "save_session", lambda *a, **kw: (_ for _ in ()).throw(AssertionError("save called")))

    result = _recover_session(fake_page, fake_context, row_id="abc123", username="u", password="p")

    assert result is True
    assert fake_page.reloaded is True
    info_msgs = _messages(log_records, logging.INFO)
    assert any("[recovery]" in m and "action=reload result=ok" in m for m in info_msgs)

