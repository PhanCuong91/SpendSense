"""Tests for app/misa/runner.py's logging (§5.3 item 2) and .env /
.gitignore credential handling (§5.3 item 3).

These exercise `_run_dry`, `_run_import`, and `main()` directly with
fakes/mocks for Playwright, `client`, and the dedup store so they run fully
offline: no real browser, no real MISA credentials, no real DB.
"""
import logging
from pathlib import Path

import pytest

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


class _Row:
    def __init__(self, id):
        self.id = id


def _planned_row(row_id, amount, account="Trust", classification="Spend"):
    row = _Row(id=row_id)
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


def test_dry_run_logs_planned_rows(log_records):
    row, classification, tx = _planned_row("row-1", 1.23)

    exit_code = runner._run_dry([(row, classification, tx)], considered=1, skipped=0)

    assert exit_code == 0
    messages = _messages(log_records)
    assert any(m.startswith("Dry run: 1 row(s) would be imported") for m in messages)
    assert (
        "[would-import] id=row-1 type=Spend amount=1.23 account=Trust datetime=08/08/2026 00:00 "
        "category=Bars & Coffee" in messages
    )


def test_imported_and_failed_log_lines_match_design_format(monkeypatch, tmp_path, log_records):
    ok_row, ok_classification, ok_tx = _planned_row("ok-1", 1.23, account="Trust")
    bad_row, bad_classification, bad_tx = _planned_row("bad-1", 4.56, account="PayLah")
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

    dedup_store = DedupStore(path=str(tmp_path / "state.json"))
    exit_code = runner._run_import(planned, considered=2, skipped=0, dedup_store=dedup_store, headed=False)

    assert exit_code == 1  # at least one row failed
    info_messages = _messages(log_records, logging.INFO)
    error_messages = _messages(log_records, logging.ERROR)

    assert "[imported] id=ok-1 amount=1.23 account=Trust datetime=08/08/2026 00:00" in info_messages
    assert (
        "[failed]   id=bad-1 amount=4.56 account=PayLah datetime=08/08/2026 00:00 "
        "reason=save button not found" in error_messages
    )
    assert "Summary: considered=2 imported=1 failed=1 skipped(already imported)=0" in info_messages

    assert dedup_store.is_imported("ok-1") is True
    assert dedup_store.is_imported("bad-1") is False


def test_summary_logged_when_credentials_missing(monkeypatch, tmp_path, log_records):
    row, classification, tx = _planned_row("row-1", 1.0)

    monkeypatch.delenv("MISA_USERNAME", raising=False)
    monkeypatch.delenv("MISA_PASSWORD", raising=False)

    def _fail_if_called():
        raise AssertionError("sync_playwright() must not be called when credentials are missing")

    monkeypatch.setattr(runner, "sync_playwright", _fail_if_called)

    dedup_store = DedupStore(path=str(tmp_path / "state.json"))
    exit_code = runner._run_import([(row, classification, tx)], considered=1, skipped=0, dedup_store=dedup_store, headed=False)

    assert exit_code == 1
    error_messages = _messages(log_records, logging.ERROR)
    assert any("MISA_USERNAME and MISA_PASSWORD must be set" in m for m in error_messages)


# ---------------------------------------------------------------------------
# Item 3: .env support for MISA_USERNAME/MISA_PASSWORD + secrets never logged
# ---------------------------------------------------------------------------


def test_dry_run_limit_caps_planned_rows(log_records, monkeypatch):
    """--limit should cap the number of rows shown/considered for import."""
    row1, _, tx1 = _planned_row("row-1", 1.0)
    row2, _, tx2 = _planned_row("row-2", 2.0)
    row3, _, tx3 = _planned_row("row-3", 3.0)
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


def test_credentials_are_never_logged(monkeypatch, tmp_path, log_records):
    row, classification, tx = _planned_row("row-1", 1.0)

    monkeypatch.setenv("MISA_USERNAME", "secret_user_xyz")
    monkeypatch.setenv("MISA_PASSWORD", "supersecretpassword123")
    monkeypatch.setattr(runner.client, "is_logged_in", lambda page: True)
    monkeypatch.setattr(runner.client, "login", lambda page, username, password: True)
    monkeypatch.setattr(runner.client, "save_session", lambda ctx, path=None: None)
    monkeypatch.setattr(runner.client, "add_transaction", lambda page, tx: MisaImportResult(success=True))
    monkeypatch.setattr(runner, "sync_playwright", _fake_sync_playwright_factory())

    dedup_store = DedupStore(path=str(tmp_path / "state.json"))
    runner._run_import([(row, classification, tx)], considered=1, skipped=0, dedup_store=dedup_store, headed=False)

    all_messages = " ".join(_messages(log_records))
    assert "secret_user_xyz" not in all_messages
    assert "supersecretpassword123" not in all_messages


def test_gitignore_covers_misa_secrets_and_session_state():
    repo_root = Path(runner.__file__).resolve().parents[2]
    content = (repo_root / ".gitignore").read_text()

    assert ".env.misa" in content
    assert "storage_state.json" in content
    assert "app.log" in content
