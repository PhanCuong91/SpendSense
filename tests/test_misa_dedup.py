from app.misa.dedup_store import DedupStore


def test_fresh_store_treats_all_ids_as_not_imported(tmp_path):
    store = DedupStore(path=tmp_path / "state.json")

    assert store.is_imported("abc-123") is False
    assert store.is_imported("does-not-exist") is False


def test_mark_imported_persists_across_reload(tmp_path):
    state_file = tmp_path / "state.json"
    store = DedupStore(path=state_file)

    store.mark_imported("abc-123", {"amount": "10.50", "account": "PayLah"})

    assert store.is_imported("abc-123") is True
    assert state_file.exists()

    reloaded = DedupStore(path=state_file)
    assert reloaded.is_imported("abc-123") is True


def test_failed_attempt_is_never_written_and_remains_eligible(tmp_path):
    state_file = tmp_path / "state.json"
    store = DedupStore(path=state_file)

    # A failed row simply never calls mark_imported(); nothing should be
    # written to disk, and the id must remain eligible for retry.
    assert store.is_imported("failed-row") is False
    assert not state_file.exists()

    reloaded = DedupStore(path=state_file)
    assert reloaded.is_imported("failed-row") is False
